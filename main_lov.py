import re
import time
import json
import threading
import requests
import queue
import asyncio
import websockets
import os
import hmac
import hashlib
import subprocess
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from functools import wraps
import uuid
from datetime import datetime

with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

app = Flask(__name__)
app.secret_key = CONFIG["secret_key"]
USERS = CONFIG["users"]

import asyncio

vibration_queues = {user: asyncio.Queue() for user in CONFIG["profiles"].keys()}
CONNECTED_USERS = {}

# ---------------- LOVENSE ----------------
import hashlib

donation_logs = {user: [] for user in CONFIG["profiles"].keys()}


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


def add_log(user, message):
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {message}"
    donation_logs[user].append(entry)
    if len(donation_logs[user]) > 200:
        donation_logs[user].pop(0)
    print(entry)


def generate_utoken(uid, secret="arina_secret_123"):
    raw = uid + secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_qr_code(user):
    profile = CONFIG["profiles"][user]
    url = "https://api.lovense.com/api/lan/getQrCode"

    uid = f"{user}_001"
    utoken = generate_utoken(uid)

    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "uname": user,
        "utoken": utoken,  # ⚠️ теперь мы сами его задаём
        "callbackUrl": "https://arinairina.duckdns.org/lovense/callback?token=arina_secret_123",
        "v": 2,
    }

    r = requests.post(url, json=payload, timeout=10)
    data = r.json()
    print("Ответ от Lovense API:", data)
    if data.get("code") == 0 and "data" in data and "qr" in data["data"]:
        return data["data"]["qr"]
    if "message" in data and str(data["message"]).startswith("http"):
        return data["message"]
    return None


@app.route("/lovense/callback", methods=["POST"])
def lovense_callback():
    data = request.json or request.form
    print("📩 Callback от Lovense:", data)

    uid = data.get("uid")
    if uid:
        CONNECTED_USERS[uid] = {
            "utoken": data.get("utoken"),
            "toys": data.get("toys", {}),
        }
        # 🔍 Отладка: выводим текущее состояние CONNECTED_USERS
        print(
            "🔐 CONNECTED_USERS сейчас:",
            json.dumps(CONNECTED_USERS, indent=2, ensure_ascii=False),
        )
        return "✅ Callback принят", 200
    return "❌ Нет uid", 400


def send_vibration_cloud(user, strength, duration):
    """Отправка вибрации через Lovense Cloud API"""
    uid = f"{user}_001"
    user_data = CONNECTED_USERS.get(uid)

    if not user_data:
        print(f"❌ [{user}] Нет данных из callback — игрушка не подключена")
        return None

    utoken = user_data.get("utoken")
    if not utoken:
        print(f"❌ [{user}] utoken пустой — пересканируй QR‑код")
        return None

    profile = CONFIG["profiles"][user]
    url = "https://api.lovense.com/api/lan/v2/command"

    payload = {
        "token": profile["DEVELOPER_TOKEN"],  # Cloud Developer Token
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": f"Vibrate:{strength}",
        "timeSec": duration,
    }

    try:
        print(f"📤 [{user}] Отправка вибрации → {payload}")  # 🔍 лог перед запросом
        r = requests.post(url, json=payload, timeout=10)
        print(f"📥 [{user}] Ответ Cloud API: {r.text}")  # 🔍 лог ответа
        data = r.json()
        return data
    except Exception as e:
        print(f"❌ [{user}] Ошибка Cloud‑вибрации:", e)
        return None


async def vibration_worker(user):
    q = vibration_queues[user]
    while True:
        try:
            strength, duration = await q.get()
            send_vibration_cloud(user, strength, duration)
            await asyncio.sleep(duration)
        except Exception as e:
            print(f"⚠️ [{user}] Ошибка в vibration_worker:", e)
        finally:
            q.task_done()


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
    print(f"⚙️ [{user}] apply_rule: сумма={amount}, текст={text}")
    rules = load_rules(user)

    for rule in rules.get("rules", []):
        if rule["min"] <= amount <= rule["max"]:
            action = rule.get("action")
            if action and action.strip():
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                with open("donations.log", "a", encoding="utf-8") as f:
                    f.write(f"{ts} | {user} | {amount} | ДЕЙСТВИЕ: {action}\n")
                update_stats(user, "actions", amount)
                return f"🎬 Действие: {action}"  # ✅ возвращаем текст

            # если нет действия, значит это вибрация
            strength = rule.get("strength", 1)
            duration = rule.get("duration", 5)
            vibration_queues[user].put_nowait((strength, duration))
            print(f"⚙️ [{user}] Вибрация: сила={strength}, время={duration}")
            update_stats(user, "vibrations", amount)
            return (
                f"🏰 Вибрация: сила={strength}, время={duration}"  # ✅ возвращаем текст
            )

    print(f"🚫 [{user}] Донат {amount} не попадает ни под одно правило — игнорируем")
    return None  # ❌ ничего не подошло


# ---------------- VIP ----------------


def update_vip(user, user_id, name=None, amount=0, event=None):
    profile = CONFIG["profiles"][user]
    vip_file = profile["vip_file"]

    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    # если заблокирован — не обновляем
    if user_id in vip_data and vip_data[user_id].get("blocked"):
        print(f"🚫 [{user}] Мембер {user_id} заблокирован — пропускаем")
        return vip_data.get(user_id)

    # если новый — создаём
    if user_id not in vip_data:
        vip_data[user_id] = {
            "name": name or "Аноним",
            "alias": "",
            "total": 0,
            "notes": "",
            "login_count": 0,
            "last_login": "",
            "blocked": False,
            "_just_logged_in": False,
        }

    # обновляем имя — только если оно ещё не задано вручную
    if name:
        current_name = vip_data[user_id].get("name", "")
        if not current_name or current_name == "Аноним":
            vip_data[user_id]["name"] = name

    # обновляем сумму
    if amount and amount > 0:
        vip_data[user_id]["total"] += amount

    # обновляем вход
    if event and event.lower() == "login":
        vip_data[user_id]["login_count"] += 1
        vip_data[user_id]["last_login"] = time.strftime("%Y-%m-%d %H:%M:%S")
        vip_data[user_id]["_just_logged_in"] = True

    with open(vip_file, "w", encoding="utf-8") as f:
        json.dump(vip_data, f, indent=2, ensure_ascii=False)

    return vip_data[user_id]   # ✅ теперь возвращаем профиль


def log_donation(text, amount):
    with open("donations.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {amount} | {text}\n")


# ---------------- ВСПОМОГАТЕЛЬНОЕ ----------------
def get_vibration_queue(user):
    q = vibration_queues.get(user)
    if not q:
        return []
    return list(q._queue)  # доступ к внутреннему списку очереди


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


def log_donation(text, amount):
    with open("donations.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {amount} | {text}\n")


# ---------------- ВСПОМОГАТЕЛЬНОЕ ----------------
def get_vibration_queue(user):
    q = vibration_queues.get(user)
    if not q:
        return []
    return list(q._queue)  # доступ к внутреннему списку очереди


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


def update_stats(user, category, points):
    today = time.strftime("%Y-%m-%d")
    stats_file = "stats.json"

    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except:
        stats = {}

    if user not in stats:
        stats[user] = {}

    if today not in stats[user]:
        stats[user][today] = {"vibrations": 0, "actions": 0, "other": 0, "total": 0}

    stats[user][today][category] += points
    stats[user][today]["total"] += points

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


processed_donations = set()


def clear_processed_donations():
    global processed_donations
    processed_donations.clear()
    print("🧹 Список обработанных донатов очищен")


async def ws_handler(websocket):
    print("🔌 WebSocket подключён")

    async for message in websocket:
        try:
            print("📩 Получено сообщение от WebSocket:", message)

            data = json.loads(message)
            text = data.get("text", "")
            name = (data.get("name") or "Аноним").strip()
            user_id = data.get("user_id")
            amount = data.get("amount")
            donation_id = data.get("donation_id")
            user = data.get("user")

            # 🔐 Проверка профиля
            if not user:
                await websocket.send("❌ Не указан профиль")
                continue
            if user not in CONFIG.get("profiles", {}):
                await websocket.send(f"❌ Профиль '{user}' не найден")
                continue

            # ⚠️ donation_id можно логировать, но не блокировать
            if not donation_id:
                print("⚠️ Нет donation_id — может быть тест или ошибка")

            # 🧠 Обработка входа/выхода
            if "event" in data:
                event = data["event"]
                user_id = data.get("user_id")
                name = data.get("name", "Аноним")
                text = data.get("text", "")

                profile = update_vip(user, user_id, name=name, event=event)

                add_log(user, f"📥 Событие: {event.upper()} | {name} ({user_id}) → {text}")

                # если это вход и профиль обновился → отправляем карточку на фронт
                if profile and profile.get("_just_logged_in"):
                    await websocket.send(json.dumps({
                        "entry": {
                            "user_id": user_id,
                            "name": profile["name"],
                            "visits": profile["login_count"],
                            "last_login": profile["last_login"],
                            "total_tips": profile["total"],
                            "notes": profile["notes"]
                        }
                    }))
                    profile["_just_logged_in"] = False  # сбрасываем флаг

                await websocket.send(f"✅ Событие {event} обработано")
                continue

            # 💸 Проверка суммы
            if not amount or amount <= 0:
                await websocket.send("ℹ️ Сообщение не содержит донат")
                continue

            # ✅ Логируем донат + действие
            action_text = apply_rule(user, amount, text)

            if action_text:
                add_log(user, f"✅ [{user}] Донат | {name} → {amount} {action_text}")
            else:
                add_log(user, f"✅ [{user}] Донат | {name} → {amount} ℹ️ Без действия")
                update_stats(user, "other", amount)

            # 👑 Обновление VIP‑листа
            if user_id:
                update_vip(user, user_id, name=name, amount=amount)

            await websocket.send("✅ Донат принят")

        except Exception as e:
            print("⚠️ Ошибка обработки:", e)
            await websocket.send("❌ Ошибка обработки")


async def ws_server():
    # запускаем воркеры для всех профилей
    for user in CONFIG["profiles"]:
        asyncio.create_task(vibration_worker(user))

    # включаем пинг каждые 30 секунд
    async with websockets.serve(
        ws_handler, "0.0.0.0", 8765, origins=None, ping_interval=30
    ):
        print("🚀 WebSocket‑сервер запущен на ws://0.0.0.0:8765 (ping каждые 30 сек)")
        await asyncio.Future()  # держим сервер живым


# ---------------- Flask Routes ----------------
@app.route("/")
@login_required
def index():
    user = session["user"]
    profile = CONFIG["profiles"][user]
    queue = get_vibration_queue(user)
    logs = donation_logs.get(user, [])
    return render_template(
        "index.html", user=user, profile=profile, queue=queue, logs=logs
    )


@app.route("/qrcode")
@login_required
def qrcode_page():
    user = session["user"]
    qr_url = get_qr_code(user)
    if not qr_url:
        return "❌ Не удалось получить QR‑код", 500
    return render_template("qrcode.html", user=user, qr_url=qr_url)


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


@app.route("/queue_data")
@login_required
def queue_data():
    user = session["user"]
    q = vibration_queues.get(user)
    if not q:
        return {"queue": []}
    return {"queue": list(q._queue)}


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/test_vibration", methods=["POST"])
@login_required
def test_vibration():
    user = session["user"]
    threading.Thread(target=send_vibration_cloud, args=(user, 1, 5)).start()
    return {"status": "ok", "message": "Вибрация отправлена ✅"}


@app.route("/stats")
@login_required
def stats_page():
    user = session["user"]
    try:
        with open("stats.json", "r", encoding="utf-8") as f:
            stats = json.load(f)
    except:
        stats = {}

    user_stats = stats.get(user, {})
    return render_template("stats.html", stats=user_stats, user=user)


@app.route("/test_rule/<int:rule_index>", methods=["POST"])
@login_required
def test_rule(rule_index):
    user = session["user"]
    rules = load_rules(user)

    if 0 <= rule_index < len(rules["rules"]):
        rule = rules["rules"][rule_index]
        strength = rule.get("strength", 1)
        duration = rule.get("duration", 5)

        print(
            f"🧪 [{user}] Тест правила {rule_index}: сила={strength}, время={duration}"
        )
        send_vibration_cloud(user, strength, duration)

        return {
            "status": "ok",
            "message": f"Правило {rule_index} проверено ✅ (сила={strength}, время={duration}s)",
        }

    return {"status": "error", "message": "❌ Правило не найдено"}, 404


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
            text=True,
        )

        if result.returncode != 0:
            print("🔥 Ошибка обновления:", result.stderr)
            return "Internal Server Error", 500

        print("✅ Обновление прошло успешно:", result.stdout)
        return "OK", 200

    except Exception as e:
        print("🔥 Ошибка в webhook:", e)
        return "Internal Server Error", 500


@app.route("/Success", methods=["GET"])
def success_page():
    return "✅ Игрушка успешно подключена!", 200


@app.route("/Error", methods=["GET"])
def error_page():
    return "❌ Ошибка подключения!", 200


@app.route("/clear_vip", methods=["POST"])
@login_required
def clear_vip():
    user = session["user"]
    vip_file = CONFIG["profiles"][user]["vip_file"]
    with open(vip_file, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2, ensure_ascii=False)
    return redirect("/vip")


@app.route("/remove_member", methods=["POST"])
@login_required
def remove_member():
    user = session["user"]
    user_id = request.form.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Нет user_id"}, 400

    vip_file = CONFIG["profiles"][user]["vip_file"]
    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    if user_id in vip_data:
        del vip_data[user_id]
        with open(vip_file, "w", encoding="utf-8") as f:
            json.dump(vip_data, f, indent=2, ensure_ascii=False)
        return {"status": "ok", "message": "Мембер удалён"}
    return {"status": "error", "message": "Мембер не найден"}, 404


@app.route("/block_member", methods=["POST"])
@login_required
def block_member():
    user = session["user"]
    user_id = request.form.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Нет user_id"}, 400

    vip_file = CONFIG["profiles"][user]["vip_file"]
    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    if user_id in vip_data:
        vip_data[user_id]["blocked"] = True
        with open(vip_file, "w", encoding="utf-8") as f:
            json.dump(vip_data, f, indent=2, ensure_ascii=False)
        return {"status": "ok", "message": "Мембер заблокирован"}
    return {"status": "error", "message": "Мембер не найден"}, 404


@app.route("/vip", methods=["GET", "POST"])
@login_required
def vip_page():
    user = session["user"]
    vip_file = CONFIG["profiles"][user]["vip_file"]

    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    # ✏️ Обработка редактирования alias и заметок
    if request.method == "POST" and "user_id" in request.form:
        user_id = request.form.get("user_id")
        if user_id in vip_data:
            vip_data[user_id]["name"] = request.form.get("name", "").strip()
            vip_data[user_id]["notes"] = request.form.get("notes", "").strip()
            with open(vip_file, "w", encoding="utf-8") as f:
                json.dump(vip_data, f, indent=2, ensure_ascii=False)
        return redirect("/vip")

    # 🔍 Поиск
    query = request.args.get("q", "").strip().lower()
    filtered = (
        {
            uid: info
            for uid, info in vip_data.items()
            if query in uid.lower()
            or query in info.get("name", "").lower()
            or query in info.get("notes", "").lower()
        }
        if query
        else vip_data
    )

    # 📋 Сортировка по сумме
    sorted_members = sorted(
        filtered.items(), key=lambda x: x[1].get("total", 0), reverse=True
    )

    return render_template("vip.html", user=user, members=sorted_members, query=query)


@app.route("/update_name", methods=["POST"])
@login_required
def update_name():
    user = session["user"]
    user_id = request.form.get("user_id")
    new_name = request.form.get("name")

    if not user_id or not new_name:
        return {"status": "error", "message": "Недостаточно данных"}, 400

    vip_file = CONFIG["profiles"][user]["vip_file"]
    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    if user_id not in vip_data:
        return {"status": "error", "message": "Мембер не найден"}, 404

    vip_data[user_id]["name"] = new_name

    with open(vip_file, "w", encoding="utf-8") as f:
        json.dump(vip_data, f, indent=2, ensure_ascii=False)

    return {"status": "ok"}


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

    # ✅ гарантируем, что у всех правил есть id
    for r in rules_data["rules"]:
        if "id" not in r:
            r["id"] = str(uuid.uuid4())

    if request.method == "POST":

        def to_int(name, default=0):
            try:
                return int(request.form.get(name, default))
            except:
                return default

        # ➕ Добавление нового правила
        if "add_rule" in request.form:
            action_type = request.form.get("action_type")
            action = request.form.get("action") or None
            if action_type == "vibration":
                action = None

            new_rule = {
                "id": str(uuid.uuid4()),  # уникальный идентификатор
                "min": to_int("min", 1),
                "max": to_int("max", 5),
                "strength": to_int("strength", 1),
                "duration": to_int("duration", 5),
                "action": action,
            }
            rules_data["rules"].append(new_rule)

        # ❌ Удаление правила
        elif "delete_rule" in request.form:
            rule_id = request.form["delete_rule"]
            rules_data["rules"] = [r for r in rules_data["rules"] if r["id"] != rule_id]

        # ✏️ Редактирование правила
        elif "edit_rule" in request.form:
            rule_id = request.form["edit_rule"]
            for r in rules_data["rules"]:
                if r["id"] == rule_id:
                    action_type = request.form.get("action_type")
                    action = request.form.get("action") or None
                    if action_type == "vibration":
                        action = None
                    r.update(
                        {
                            "min": int(request.form["min"]),
                            "max": int(request.form["max"]),
                            "strength": int(request.form["strength"]),
                            "duration": int(request.form["duration"]),
                            "action": action,
                        }
                    )
                    break

        # 💾 Сохраняем обновлённые правила
        with open(rules_file, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, indent=2, ensure_ascii=False)

        return redirect("/rules")

    # ✅ Сортировка перед отдачей в шаблон
    sorted_rules = sorted(rules_data["rules"], key=lambda r: r["min"])

    return render_template(
        "rules.html", rules=sorted_rules, default=rules_data["default"]
    )


@app.route("/logs")
@login_required
def logs_page():
    user = session["user"]
    return render_template("logs.html", logs=donation_logs.get(user, []))


def get_recent_logins(user):
    vip_file = CONFIG["profiles"][user]["vip_file"]
    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    entries = []
    for uid, info in vip_data.items():
        if info.get("_just_logged_in"):
            entries.append(
                {
                    "user_id": uid,
                    "name": info.get("name", "Аноним"),
                    "notes": info.get("notes", ""),
                    "is_new": False,
                }
            )
            info["_just_logged_in"] = False  # сбрасываем флаг

    # сохраняем сброшенный флаг
    with open(vip_file, "w", encoding="utf-8") as f:
        json.dump(vip_data, f, indent=2, ensure_ascii=False)

    return entries


@app.route("/logs_data")
@login_required
def logs_data():
    user = session["user"]
    return {"logs": donation_logs.get(user, []), "entries": get_recent_logins(user)}


@app.route("/clear_logs", methods=["POST"])
@login_required
def clear_logs():
    user = session["user"]
    donation_logs[user] = []  # очищаем только логи текущего пользователя
    return redirect("/logs")


@app.route("/clear_queue", methods=["POST"])
@login_required
def clear_queue():
    user = session["user"]
    q = vibration_queues.get(user)
    if q:
        while not q.empty():
            q.get_nowait()
            q.task_done()
    return {"status": "ok", "message": "Очередь очищена ✅"}


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
