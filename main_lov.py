import re
import time
import json
import threading
import requests
import queue
import asyncio
import websockets
import os
from flask import request
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from functools import wraps
import subprocess
import hmac
import hashlib
import telegram

def send_vibration_to_user(user, strength, duration):
    profile = CONFIG["profiles"][user]
    token = profile["telegram_bot_token"]
    chat_id = profile["telegram_chat_id"]
    bot = telegram.Bot(token=token)
    message = f"VIBRATE:{strength};DURATION:{duration}"
    bot.send_message(chat_id=chat_id, text=message)

def send_command(user, command):
    """
    Универсальная отправка команды в Lovense Cloud API
    command может быть строкой: "Vibrate:3", "Vibrate:0", "Rotate:2", "Stop"
    """
    profile = CONFIG["profiles"][user]
    token = profile["DEVELOPER_TOKEN"]

    url = "https://api.lovense.com/api/lan/sendCommand"
    headers = {"Content-Type": "application/json"}
    payload = {
        "token": token,
        "command": command
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        data = response.json()
        print(f"📤 [{user}] Команда {command} → {data}")
        return data
    except Exception as e:
        print(f"❌ [{user}] Ошибка при отправке команды {command}:", e)
        return None


with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)


app = Flask(__name__)
app.secret_key = CONFIG["secret_key"]
USERS = CONFIG["users"]
vibration_queues = {user: queue.Queue() for user in CONFIG["profiles"].keys()}


def vibration_worker(user):
    q = vibration_queues[user]
    while True:
        strength, duration = q.get()
        print(f"📥 [{user}] Новый донат в очереди: сила {strength}, время {duration}")
        send_vibration_via_api
        elapsed = 0
        while elapsed < duration:
            time.sleep(0.5)
            elapsed += 0.5
            print(f"⏳ [{user}] Осталось: {max(0, duration - elapsed):.1f} сек")
        # стоп после выполнения
        q.task_done()

# Запуск воркеров для каждого профиля
for user in CONFIG["profiles"].keys():
    threading.Thread(target=vibration_worker, args=(user,), daemon=True).start()

# ---------------- LOVENSE ----------------

def get_qr_code(user):
    profile = CONFIG["profiles"][user]
    url = "https://api.lovense.com/api/lan/getQrCode"

    # твой уникальный ID и имя пользователя (можешь придумать сама)
    uid = f"{user}_001"
    uname = user

    # опционально: utoken для верификации (uid + твой секрет)
    salt = "arina_secret123"
    utoken = hashlib.md5((uid + salt).encode()).hexdigest()

    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "uname": uname,
        "utoken": utoken,
        "callbackUrl": "https://arinairina.duckdns.org/lovense/callback?token=arina_secret_123",
        "v": 2
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        if data.get("code") == 0:
            # API возвращает ссылку на QR‑код (URL картинки)
            return data["message"]
        else:
            print("Ошибка API:", data)
            return None
    except Exception as e:
        print("Ошибка при запросе QR‑кода:", e)
        return None
    
def send_vibration_via_api(user, strength, duration):
    profile = CONFIG["profiles"][user]
    token = profile["DEVELOPER_TOKEN"]

    url = "https://api.lovense.com/api/lan/sendCommand"
    headers = {"Content-Type": "application/json"}

    vibrate_payload = {
        "token": token,
        "command": f"Vibrate:{strength}"
    }
    stop_payload = {
        "token": token,
        "command": "Vibrate:0"
    }

    try:
        print(f"📤 [{user}] API‑вибрация: сила {strength}, длительность {duration}")
        requests.post(url, json=vibrate_payload, headers=headers, timeout=5)
        time.sleep(duration)
        requests.post(url, json=stop_payload, headers=headers, timeout=5)
        print(f"⏹ [{user}] Вибрация остановлена")
    except Exception as e:
        print(f"❌ [{user}] Ошибка API:", e)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper

@app.route("/lovense/callback", methods=["GET", "POST"])
def lovense_callback():
    if request.method == "POST":
        data = request.json or request.form
        print("📩 Callback от Lovense:", data)
        return "OK", 200
    else:
        return "Callback работает (GET)", 200

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
    profile = CONFIG["profiles"][user]

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

            # 🔁 Выбор способа вибрации
            if profile.get("use_telegram_bridge"):
                send_vibration_to_user(user, strength, duration)
            elif profile.get("use_api_bridge"):
                send_vibration_via_api(user, strength, duration)
            else:
                vibration_queues[user].put((strength, duration))

            return

    # 🔁 Если ни одно правило не подошло — применяем default
    strength, duration = rules["default"]
    if profile.get("use_telegram_bridge"):
        send_vibration_to_user(user, strength, duration)
    else:
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


def clear_processed_donations():
    global processed_donations
    processed_donations.clear()
    print("🧹 Список обработанных донатов очищен")


async def ws_handler(websocket):
    print("🔌 WebSocket подключён")

    async for message in websocket:
        print(f"📥 Получено сообщение: {message}")
        await websocket.send("✅ Сервер получил сообщение")

        try:
            data = json.loads(message)
            text = data.get("text", "")
            name = (data.get("name") or "Аноним").strip()
            user_id = data.get("user_id") or try_extract_user_id_from_text(text)
            amount = fallback_amount(text, data.get("amount"))
            donation_id = data.get("donation_id")
            user = data.get("user")

            # --- определяем профиль ---
            if not user or user not in CONFIG["profiles"]:
                await websocket.send("❌ Неизвестный профиль")
                continue

            # --- проверка на повторы ---
            if donation_id:
                if donation_id in processed_donations:
                    print(f"⏩ Донат {donation_id} уже обработан — пропускаем")
                    await websocket.send("ℹ️ Донат уже был учтён")
                    continue
                processed_donations.add(donation_id)

            # --- обработка доната ---
            if amount and amount > 0:
                log_donation(text, amount)
                print(f"✅ [{user}] Донат | {name} → {amount}")
                apply_rule(user, amount, text)

                if user_id:
                    print(f"👤 [{user}] Обновление VIP: {user_id} | {name} → {amount}")
                    update_vip_list(user, user_id, name, amount)

                await websocket.send("✅ Донат принят")
            else:
                await websocket.send("ℹ️ Сообщение не содержит донат/подарок")

        except Exception as e:
            print("⚠️ Ошибка обработки:", e)
            try:
                await websocket.send("❌ Ошибка обработки сообщения")
            except:
                pass

# ---------------- WebSocket ----------------

processed_donations = set()

def clear_processed_donations():
    global processed_donations
    processed_donations.clear()
    print("🧹 Список обработанных донатов очищен")

async def ws_handler(websocket):
    print("🔌 WebSocket подключён")
    async for message in websocket:
        print(f"📥 Получено сообщение: {message}")
        await websocket.send("✅ Сервер получил сообщение")
        try:
            data = json.loads(message)
            text = data.get("text", "")
            name = (data.get("name") or "Аноним").strip()
            user_id = data.get("user_id") or try_extract_user_id_from_text(text)
            amount = fallback_amount(text, data.get("amount"))
            donation_id = data.get("donation_id")
            user = data.get("user")

            if not user or user not in CONFIG["profiles"]:
                await websocket.send("❌ Неизвестный профиль")
                continue

            if donation_id:
                if donation_id in processed_donations:
                    print(f"⏩ Донат {donation_id} уже обработан — пропускаем")
                    await websocket.send("ℹ️ Донат уже был учтён")
                    continue
                processed_donations.add(donation_id)

            if amount and amount > 0:
                log_donation(text, amount)
                print(f"✅ [{user}] Донат | {name} → {amount}")
                apply_rule(user, amount, text)

                if user_id:
                    print(f"👤 [{user}] Обновление VIP: {user_id} | {name} → {amount}")
                    update_vip_list(user, user_id, name, amount)

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
    async with websockets.serve(
        ws_handler,
        "0.0.0.0",
        8765,
        origins=None,
        ping_interval=None
    ):
        print("🚀 WebSocket‑сервер запущен на ws://0.0.0.0:8765")
        await asyncio.Future()


# ---------------- Flask Routes ----------------

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

@app.route("/hook", methods=["POST"])
def hook():
    try:
        signature = request.headers.get("X-Hub-Signature-256")
        secret = CONFIG["webhook_secret"].encode()
        body = request.data
        expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature or "", expected):
            print("❌ Неверный секрет")
            return "Forbidden", 403

        data = request.get_json(silent=True)
        print("📩 Пришёл webhook:", data)

        result = subprocess.run(
            ["bash", "-lc", "cd /root/arina-project && git pull && poetry install"],
            capture_output=True,
            text=True
        )


        if result.returncode != 0:
            print("🔥 Ошибка обновления:", result.stderr)
            return "Internal Server Error", 500

        print("✅ Обновление прошло успешно:", result.stdout)
        return "OK", 200

    except Exception as e:
        print("🔥 Ошибка в webhook:", e)
        return "Internal Server Error", 500

@app.route("/rules", methods=["GET", "POST"])
@login_required
def rules():
    profile = CONFIG["profiles"][session["user"]]
    rules_file = profile["rules_file"]

    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            rules_data = json.load(f)
    except:
        rules_data = {"default": [1, 5], "rules": []}

    if request.method == "POST":
        def to_int(name, default=0):
            try:
                return int(request.form.get(name, default))
            except:
                return default

        if "add_rule" in request.form:
            new_rule = {
                "min": to_int("min", 1),
                "max": to_int("max", 5),
                "strength": to_int("strength", 1),
                "duration": to_int("duration", 5),
                "action": request.form.get("action") or None
            }
            rules_data["rules"].append(new_rule)

        elif "delete_rule" in request.form:
            idx = int(request.form["delete_rule"])
            if 0 <= idx < len(rules_data["rules"]):
                rules_data["rules"].pop(idx)

        elif "edit_rule" in request.form:
            idx = int(request.form["edit_rule"])
            if 0 <= idx < len(rules_data["rules"]):
                rules_data["rules"][idx] = {
                    "min": int(request.form["min"]),
                    "max": int(request.form["max"]),
                    "strength": int(request.form["strength"]),
                    "duration": int(request.form["duration"]),
                    "action": request.form["action"] or None
                }

        with open(rules_file, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, indent=2, ensure_ascii=False)

        return redirect("/rules")

    return render_template("rules.html", rules=rules_data["rules"], default=rules_data["default"])

@app.route("/")
@login_required
def index():
    profile = CONFIG["profiles"][session["user"]]
    return render_template("index.html", user=session.get("user"), profile=profile)

@app.route("/qrcode")
@login_required
def qrcode_page():
    user = session["user"]
    qr_url = get_qr_code(user)
    if not qr_url:
        return "❌ Не удалось получить QR‑код", 500
    return render_template("qrcode.html", user=user, qr_url=qr_url)

@app.route("/test_vibration")
@login_required
def test_vibration():
    user = session["user"]
    send_vibration_to_user(user, strength=3, duration=5)
    return "✅ Тест‑вибрация отправлена"


# ---------------- ЗАПУСК ----------------

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False)

def run_websocket():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_server())
    loop.run_forever()

def monitor_flag():
    print("🚀 Программа запущена. Ожидание донатов через WebSocket...")
    try:
        while True:
            if os.path.exists("reset.flag"):
                clear_processed_donations()
                os.remove("reset.flag")
            time.sleep(60)
    except KeyboardInterrupt:
        print("⏹ Остановка программы")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=run_websocket, daemon=True).start()
    monitor_flag()

