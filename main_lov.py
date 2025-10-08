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


SECRET_TOKEN = "arina_secret_123"
DEV_TOKEN = "qMGjSjH0zrDh-sgTCv5LLd4w3KQQWiKt8VWSlxHlsTkP5zT1YRh0NDMEhVj-rkOx"

app = Flask(__name__)
app.secret_key = "G7{nOqJKBaAnS6BWw9Cl2{Nn~S~78x|m"  # можно хранить в config.json
USERS = {
    "arina": "89068993567fA1!",
    "irishka": "1122334455fA!"
}
toy_info = {}
vibration_queue = queue.Queue()

# ---------------- ВИБРАЦИЯ ----------------
def save_queue_snapshot():
    try:
        with open("vibration_queue.json", "w", encoding="utf-8") as f:
            snapshot = list(vibration_queue.queue)
            json.dump([{"strength": s, "duration": d} for s, d in snapshot], f)
    except Exception as e:
        print("⚠️ Ошибка сохранения очереди:", e)

def vibrate_now(strength):
    if not toy_info:
        print("❌ Игрушка не подключена")
        return
    domain = toy_info["domain"]
    port = toy_info["httpPort"]
    toy_id = list(toy_info["toys"].keys())[0]
    url = f"http://{domain}:{port}/Vibrate"
    params = {"t": toy_id, "v": strength, "sec": 0}
    requests.get(url, params=params)

def vibrate(strength, duration):
    vibration_queue.put((strength, duration))

def stop():
    if not toy_info:
        return
    domain = toy_info["domain"]
    port = toy_info["httpPort"]
    toy_id = list(toy_info["toys"].keys())[0]
    url = f"http://{domain}:{port}/Vibrate"
    params = {"t": toy_id, "v": 0}
    requests.get(url, params=params)

def vibration_worker():
    while True:
        save_queue_snapshot()
        strength, duration = vibration_queue.get()
        print(f"🚀 Вибрация: сила {strength}, длительность {duration} сек")
        vibrate_now(strength)
        elapsed = 0
        while elapsed < duration:
            time.sleep(0.5)
            elapsed += 0.5
            print(f"⏳ Осталось: {max(0, duration - elapsed):.1f} сек")
        stop()
        vibration_queue.task_done()
        save_queue_snapshot()

# ---------------- LOVENSE ----------------
def get_qr_code(dev_token, uid="arina", username="Arina"):
    url = "https://api.lovense.com/api/lan/getQrCode"
    params = {"token": dev_token, "uid": uid, "username": username}
    r = requests.post(url, data=params)
    data = r.json()
    if data.get("code") == 0:
        return data["message"]   # 👉 просто возвращаем ссылку
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
    global toy_info
    token = request.args.get("token")
    if token != SECRET_TOKEN:
        return jsonify({"status": "error", "message": "unauthorized"}), 403
    toy_info = request.json
    print("🔗 Игрушка подключена:")
    print(json.dumps(toy_info, indent=2, ensure_ascii=False))
    with open("toy_status.json", "w", encoding="utf-8") as f:
        json.dump({
            "toy_id": list(toy_info["toys"].keys())[0],
            "domain": toy_info["domain"],
            "port": toy_info["httpPort"]
        }, f)
    return jsonify({"status": "ok"})

# ---------------- ПРАВИЛА ----------------
def load_rules():
    try:
        with open("rules.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"default": [1, 5], "rules": []}

def apply_rule(amount, text):
    rules = load_rules()
    for rule in rules["rules"]:
        if rule["min"] <= amount <= rule["max"]:
            if rule.get("action"):  
                # 👉 Если у правила есть действие — пишем его в лог
                ts = time.strftime('%Y-%m-%d %H:%M:%S')
                with open("donations.log", "a", encoding="utf-8") as f:
                    f.write(f"{ts} | {amount} | ДЕЙСТВИЕ: {rule['action']}\n")
                print(f"🎬 Действие для доната {amount}: {rule['action']}")
                return
            else:
                # 👉 Если действия нет — запускаем вибрацию
                strength = rule.get("strength", 1)
                duration = rule.get("duration", 5)
                vibrate(strength, duration)

                return

    # 👉 Если ни одно правило не подошло — берём дефолт
    strength, duration = rules["default"]
    vibrate(strength, duration)

# ---------------- VIP ----------------
def update_vip_list(user_id, name, amount):
    try:
        with open("vip_donaters.json", "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    if user_id not in vip_data:
        vip_data[user_id] = {
            "name": name,
            "alias": "",
            "total": 0
        }

    vip_data[user_id]["total"] += amount
    if name:
        vip_data[user_id]["name"] = name

    with open("vip_donaters.json", "w", encoding="utf-8") as f:
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

def clear_processed_donations():
    global processed_donations
    processed_donations.clear()
    print("🧹 Список обработанных донатов очищен")



async def ws_handler(websocket):
    print("🔌 WebSocket подключён")
    async for message in websocket:
        print(f"📥 Получено сообщение: {message}")
        try:
            data = json.loads(message)
            text = data.get("text", "")
            name = (data.get("name") or "Аноним").strip()
            user_id = data.get("user_id") or try_extract_user_id_from_text(text)
            amount = fallback_amount(text, data.get("amount"))
            donation_id = data.get("donation_id")

            # --- проверка на повторы ---
            if donation_id:
                if donation_id in processed_donations:
                    print(f"⏩ Донат {donation_id} уже обработан — пропускаем")
                    await websocket.send("ℹ️ Донат уже был учтён")
                    continue
                processed_donations.add(donation_id)

            if amount:
                log_donation(text, amount)  # без donation_id
                print(f"✅ Донат | {name} → {amount}")
                apply_rule(amount, text)

                if user_id:
                    print(f"👤 Обновление VIP: {user_id} | {name} → {amount}")
                    update_vip_list(user_id, name, amount)

                await websocket.send("✅ Донат принят")
            else:
                await websocket.send("ℹ️ Сообщение не содержит донат/подарок")

        except Exception as e:
            print("⚠️ Ошибка обработки:", e)
            try:
                await websocket.send("❌ Ошибка обработки сообщения")
            except:
                pass


async def ws_server():
    async with websockets.serve(ws_handler, "localhost", 8765):
        print("🚀 WebSocket‑сервер запущен на ws://localhost:8765")
        await asyncio.Future()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")
        if user in USERS and USERS[user] == pwd:
            session["user"] = user
            return redirect(url_for("index"))
        return render_template("login.html", error="Неверный логин или пароль")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", user=session.get("user"))


# ---------------- ЗАПУСК ----------------
if __name__ == "__main__":

    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True).start()
    threading.Thread(target=vibration_worker, daemon=True).start()

    def run_ws_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ws_server())
        loop.run_forever()

    threading.Thread(target=run_ws_server, daemon=True).start()

    print("🚀 Программа запущена. Ожидание донатов через WebSocket...")

    try:
        while True:
            # 👉 проверяем флажок от GUI
            if os.path.exists("reset.flag"):
                clear_processed_donations()
                os.remove("reset.flag")
            time.sleep(60)
    except KeyboardInterrupt:
        print("⏹ Остановка программы")
