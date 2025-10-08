import re
import time
import json
import threading
import requests
import queue
import asyncio
import websockets
import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from functools import wraps


with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

app = Flask(__name__)
app.secret_key = CONFIG["secret_key"]
USERS = CONFIG["users"]
vibration_queues = {user: queue.Queue() for user in CONFIG["profiles"].keys()}
toys = {}

def vibrate_for(user, strength, duration):
    toy_info = toys.get(user)
    if not toy_info:
        print(f"❌ Игрушка {user} не подключена")
        return
    domain = toy_info["domain"]
    port = toy_info["httpPort"]
    toy_id = list(toy_info["toys"].keys())[0]
    url = f"http://{domain}:{port}/Vibrate"
    params = {"t": toy_id, "v": strength, "sec": duration}
    try:
        requests.get(url, params=params, timeout=5)
    except Exception as e:
        print(f"⚠️ [{user}] Ошибка отправки вибрации:", e)

def vibration_worker(user):
    q = vibration_queues[user]
    while True:
        strength, duration = q.get()
        print(f"📥 [{user}] Новый донат в очереди: сила {strength}, время {duration}")
        vibrate_for(user, strength, duration)
        elapsed = 0
        while elapsed < duration:
            time.sleep(0.5)
            elapsed += 0.5
            print(f"⏳ [{user}] Осталось: {max(0, duration - elapsed):.1f} сек")
        # стоп после выполнения
        vibrate_for(user, 0, 0)
        q.task_done()

# Запуск воркеров для каждого профиля
for user in CONFIG["profiles"].keys():
    threading.Thread(target=vibration_worker, args=(user,), daemon=True).start()

# ---------------- LOVENSE ----------------
def get_qr_code(user):
    profile = CONFIG["profiles"][user]
    url = "https://api.lovense.com/api/lan/getQrCode"
    params = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": profile["UID"],
        "username": profile["UNAME"],
    }
    r = requests.post(url, data=params)
    data = r.json()
    if data.get("code") == 0:
        return data["message"]
    else:
        print("Ошибка API:", data)
        return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper

@app.route("/lovense/callback", methods=["POST"])
def lovense_callback():
    token = request.args.get("token")
    user = request.args.get("user")  # 👉 ?user=arina или ?user=podruzhka

    if token != CONFIG["secret_token"]:
        return jsonify({"status": "error", "message": "unauthorized"}), 403

    if user not in CONFIG["profiles"]:
        return jsonify({"status": "error", "message": "unknown user"}), 400

    data = request.json
    if not data or "toys" not in data or not data["toys"]:
        return jsonify({"status": "error", "message": "no toys in payload"}), 400
    if "domain" not in data or "httpPort" not in data:
        return jsonify({"status": "error", "message": "missing domain/httpPort"}), 400

    toys[user] = data
    print(f"🔗 Игрушка подключена для {user}:")
    print(json.dumps(toys[user], indent=2, ensure_ascii=False))

    # сохраняем статус отдельно для каждой
    status_file = f"toy_status_{user}.json"
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "toy_id": list(toys[user]["toys"].keys())[0],
                "domain": toys[user]["domain"],
                "port": toys[user]["httpPort"],
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    return jsonify({"status": "ok"})




# ---------------- ПРАВИЛА ----------------
def load_rules(user):
    profile = CONFIG["profiles"][user]
    rules_file = profile["rules_file"]
    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"default": [1, 5], "rules": []}

def apply_rule(user, amount, text):
    rules = load_rules(user)
    for rule in rules["rules"]:
        if rule["min"] <= amount <= rule["max"]:
            if rule.get("action"):
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                with open("donations.log", "a", encoding="utf-8") as f:
                    f.write(f"{ts} | {user} | {amount} | ДЕЙСТВИЕ: {rule['action']}\n")
                print(f"🎬 [{user}] Действие для доната {amount}: {rule['action']}")
                return
            strength = rule.get("strength", 1)
            duration = rule.get("duration", 5)
            vibration_queues[user].put((strength, duration))
            return

    strength, duration = rules["default"]
    vibration_queues[user].put((strength, duration))

# ---------------- VIP ----------------
def update_vip_list(user, user_id, name, amount):
    profile = CONFIG["profiles"][user]
    vip_file = profile["vip_file"]

    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    if user_id not in vip_data:
        vip_data[user_id] = {"name": name, "alias": "", "total": 0}

    vip_data[user_id]["total"] += amount
    if name:
        vip_data[user_id]["name"] = name

    with open(vip_file, "w", encoding="utf-8") as f:
        json.dump(vip_data, f, indent=2, ensure_ascii=False)


def log_donation(text, amount):
    with open("donations.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {amount} | {text}\n")


# ---------------- ВСПОМОГАТЕЛЬНОЕ ----------------
def fallback_amount(text, amount):
    if amount is None:
        m = re.search(r"(\d+)", text)
        if m:
            return int(m.group(1))
        if "подарил" in text.lower():
            return 1
    return amount


def try_extract_user_id_from_text(text):
    m_hex = re.search(r"\b([0-9a-f]{32})\b", text, re.IGNORECASE)
    if m_hex:
        return m_hex.group(1)
    m_nonopan = re.search(r"nonopan(\d{1,7})", text, re.IGNORECASE)
    if m_nonopan:
        return m_nonopan.group(1)
    return None


# --- список уже обработанных донатов ---
processed_donations = set()

