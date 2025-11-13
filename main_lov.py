import re
import time
import json
import threading
import requests
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
import shutil

with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# 🔑 глобальная переменная для режима работы
CURRENT_MODE = {"value": "private"}  # может быть "private" или "public"

app = Flask(__name__)
app.secret_key = CONFIG["secret_key"]
USERS = CONFIG["users"]

vibration_queues = {profile_key: asyncio.Queue() for profile_key in CONFIG["profiles"].keys()}
CONNECTED_USERS = {}

# ---------------- LOVENSE ----------------

def handle_donation(profile_key, sender, amount, text):
    sender_name = sender or "Анонимно"
    result = apply_rule(profile_key, amount, text) or ""
    add_log(profile_key, f"{sender_name} → {amount} {result}")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


def load_logs_from_file(profile_key):
    log_file = f"donations_{profile_key}.log"
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []
# при старте заполняем donation_logs из файлов каждого профиля
donation_logs = {}

for profile_key in CONFIG["profiles"].keys():
    donation_logs[profile_key] = load_logs_from_file(profile_key)


def add_log(profile_key, message):
    ts = datetime.now().strftime("%d-%m-%y %H:%M")
    entry = f"{ts} | {message}"

    log_file = f"donations_{profile_key}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

    if profile_key not in donation_logs:
        donation_logs[profile_key] = []
    donation_logs[profile_key].append(entry)
    if len(donation_logs[profile_key]) > 200:
        donation_logs[profile_key].pop(0)

    print(entry)

def generate_utoken(uid, secret="arina_secret_123"):
    raw = uid + secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_qr_code(profile_key):
    profile = CONFIG["profiles"][profile_key]
    url = "https://api.lovense.com/api/lan/getQrCode"

    uid = profile["uid"]
    utoken = generate_utoken(uid)
    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "uname": profile["uname"],
        "utoken": utoken,
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

def send_vibration_cloud(profile_key, strength, duration):
    profile = CONFIG["profiles"][profile_key]
    uid = profile["uid"]
    user_data = CONNECTED_USERS.get(uid)
    if not user_data:
        print(f"❌ [{profile_key}] Нет данных из callback — игрушка не подключена")
        return None
    utoken = user_data.get("utoken")
    if not utoken:
        print(f"❌ [{profile_key}] utoken пустой — пересканируй QR‑код")
        return None

    url = "https://api.lovense.com/api/lan/v2/command"
    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": f"Vibrate:{strength}",
        "timeSec": duration,
    }
    try:
        print(f"📤 [{profile_key}] Отправка вибрации → {payload}")
        r = requests.post(url, json=payload, timeout=10)
        print(f"📥 [{profile_key}] Ответ Cloud API: {r.text}")
        return r.json()
    except Exception as e:
        print(f"❌ [{profile_key}] Ошибка Cloud‑вибрации:", e)
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

CONNECTED_SOCKETS = set()

async def vibration_worker(profile_key):
    q = vibration_queues[profile_key]
    while True:
        try:
            strength, duration = await q.get()
            try:
                send_vibration_cloud(profile_key, strength, duration)
            except Exception as e:
                print(f"❌ [{profile_key}] Ошибка Cloud‑вибрации:", e)

            # Берём имя профиля из ключа конфига
            target_user = profile_key.split("_")[0]

            msg = json.dumps({
                "vibration": {
                    "strength": strength,
                    "duration": duration,
                    "target": target_user  # ← совпадает с {{ user }} на фронте
                }
            })
            print(f"📡 [{profile_key}] Отправляем фронту: {msg}")
            for ws in list(CONNECTED_SOCKETS):
                try:
                    await ws.send(msg)
                except:
                    CONNECTED_SOCKETS.discard(ws)

            await asyncio.sleep(duration)

        except Exception as e:
            print(f"⚠️ [{profile_key}] Ошибка в vibration_worker:", e)
        finally:
            q.task_done()


# ---------------- ПРАВИЛА ----------------
def load_rules(profile_key):
    profile = CONFIG["profiles"][profile_key]
    rules_file = profile["rules_file"]
    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"default": [1, 5], "rules": []}

def apply_rule(profile_key, amount, text):
    rules = load_rules(profile_key)
    for rule in rules.get("rules", []):
        if rule["min"] <= amount <= rule["max"]:
            action = rule.get("action")
            if action and action.strip():
                update_stats(profile_key, "actions", amount)  # см. блок ниже
                return f"🎬 Действие: {action}"

            strength = rule.get("strength", 1)
            duration = rule.get("duration", 5)
            vibration_queues[profile_key].put_nowait((strength, duration))
            update_stats(profile_key, "vibrations", amount)
            return f"🏰 Вибрация: сила={strength}, время={duration}"
    return None
# ---------------- VIP ----------------


def update_vip(profile_key, user_id, name=None, amount=0, event=None):
    profile = CONFIG["profiles"][profile_key]
    vip_file = profile["vip_file"]
    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    if user_id in vip_data and vip_data[user_id].get("blocked"):
        print(f"🚫 [{profile_key}] Мембер {user_id} заблокирован — пропускаем")
        return vip_data.get(user_id)

    # если новый — создаём
    if user_id not in vip_data:
        vip_data[user_id] = {
            "name": name or "Аноним",
            "alias": "",
            "total": 0,
            "notes": "",
            "login_count": 0,
            "last_login": "",   # будет пусто
            "_previous_login": "",
            "blocked": False,
            "_just_logged_in": True,
        }

    # обновляем имя, если нужно
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

        # сохраняем старый last_login в _previous_login
        old_login = vip_data[user_id].get("last_login")
        if old_login:
            vip_data[user_id]["_previous_login"] = old_login

        # обновляем last_login на текущее время
        vip_data[user_id]["last_login"] = time.strftime("%Y-%m-%d %H:%M:%S")
        vip_data[user_id]["_just_logged_in"] = True

        try:
            msg = json.dumps({"vip_update": True, "user_id": user_id})
            for ws in list(CONNECTED_SOCKETS):
                try:
                    asyncio.create_task(ws.send(msg))
                except:
                    CONNECTED_SOCKETS.discard(ws)
        except Exception as e:
            print(f"⚠️ Ошибка рассылки vip_update: {e}")

    # сохраняем файл
    with open(vip_file, "w", encoding="utf-8") as f:
        json.dump(vip_data, f, indent=2, ensure_ascii=False)

    return vip_data[user_id]


def update_stats(profile_key, category, amount):
    stats_file = f"stats_{profile_key}.json"
    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except FileNotFoundError:
        stats = {}

    day = datetime.now().strftime("%d-%m-%y")
    if day not in stats:
        stats[day] = {"vibrations": 0, "actions": 0, "other": 0, "total": 0}

    if category == "vibrations":
        stats[day]["vibrations"] += 1
    elif category == "actions":
        stats[day]["actions"] += 1
    else:
        stats[day]["other"] += 1

    stats[day]["total"] += 1

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


# ---------------- ВСПОМОГАТЕЛЬНОЕ ----------------
def get_vibration_queue(profile_key):
    q = vibration_queues.get(profile_key)
    if not q:
        return []
    return list(q._queue)

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
def load_stats(profile_key):
    stats_file = f"stats_{profile_key}.json"
    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def build_stats_from_logs(profile_key):
    stats = {}
    log_file = f"donations_{profile_key}.log"
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                date = line.split(" | ")[0].strip()
                if date not in stats:
                    stats[date] = {"vibrations": 0, "actions": 0, "other": 0, "total": 0}
                if "🏰" in line:
                    stats[date]["vibrations"] += 1
                elif "🎬" in line:
                    stats[date]["actions"] += 1
                else:
                    stats[date]["other"] += 1
                stats[date]["total"] += 1
    except FileNotFoundError:
        pass
    return stats

def update_stats(profile_key, category, points):
    today = time.strftime("%Y-%m-%d")
    stats_file = f"stats_{profile_key}.json"
    stats = load_stats(profile_key)

    if today not in stats:
        stats[today] = {"vibrations": 0, "actions": 0, "other": 0, "total": 0}

    stats[today][category] += points
    stats[today]["total"] += points

    # 📂 делаем резервную копию перед записью
    if os.path.exists(stats_file):
        backup_name = f"{stats_file}.{today}.bak"
        shutil.copy(stats_file, backup_name)

    # безопасная запись через временный файл
    tmp_file = stats_file + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, stats_file)

def extract_strength(text):
    m = re.search(r"сила[:=]\s*(\d+)", text)
    return int(m.group(1)) if m else None

def extract_duration(text):
    m = re.search(r"время[:=]\s*(\d+)", text)
    return int(m.group(1)) if m else None


async def ws_handler(websocket):
    print("🔌 WebSocket подключён")
    CONNECTED_SOCKETS.add(websocket)
    try:
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

                mode = CURRENT_MODE["value"]  # private / public
                profile_key = f"{user}_{mode}"

                if profile_key not in CONFIG.get("profiles", {}):
                    await websocket.send(f"❌ Профиль '{profile_key}' не найден")
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

                    profile = update_vip(profile_key, user_id, name=name, event=event)

                    add_log(
                        profile_key,
                        f"📥 Событие: {event.upper()} | {name} ({user_id}) → {text}",
                    )

                    # если это вход и профиль обновился → отправляем карточку на фронт
                    if profile and profile.get("_just_logged_in"):
                        await websocket.send(
                            json.dumps(
                                {
                                    "entry": {
                                        "user_id": user_id,
                                        "name": profile["name"],
                                        "visits": profile["login_count"],
                                        "last_login": profile["_previous_login"],
                                        "total_tips": profile["total"],
                                        "notes": profile["notes"],
                                    }
                                }
                            )
                        )
                        profile["_just_logged_in"] = False  # сбрасываем флаг

                    await websocket.send(f"✅ Событие {event} обработано")
                    continue

                # 💸 Проверка суммы
                if not amount or amount <= 0:
                    await websocket.send("ℹ️ Сообщение не содержит донат")
                    continue

                # ✅ Логируем донат + действие
                action_text = apply_rule(profile_key, amount, text)

                if action_text:
                    add_log(
                        profile_key, f"✅ [{user}] Донат | {name} → {amount} {action_text}"
                    )
                else:
                    add_log(
                        profile_key, f"✅ [{user}] Донат | {name} → {amount} ℹ️ Без действия"
                    )
                    update_stats(profile_key, "other", amount)

                # 👑 Обновление VIP‑листа
                if user_id:
                    profile = update_vip(profile_key, user_id, name=name, amount=amount)

                    # рассылаем событие vip_update для обновления карточки
                    try:
                        msg = json.dumps({
                            "vip_update": True,
                            "user_id": user_id,
                            "profile_key": profile_key
                        })
                        for ws in list(CONNECTED_SOCKETS):
                            try:
                                asyncio.create_task(ws.send(msg))
                            except:
                                CONNECTED_SOCKETS.discard(ws)
                    except Exception as e:
                        print(f"⚠️ Ошибка рассылки vip_update (donation): {e}")

                await websocket.send("✅ Донат принят")

            except Exception as e:
                print("⚠️ Ошибка обработки:", e)
                await websocket.send("❌ Ошибка обработки")

    finally:
        # 🔌 Убираем клиента из списка при отключении
        CONNECTED_SOCKETS.discard(websocket)
        print("🔌 WebSocket отключён")


async def ws_server():
    # запускаем воркеры для всех профилей
    for profile_key in CONFIG["profiles"]:
        asyncio.create_task(vibration_worker(profile_key))

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
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    profile = CONFIG["profiles"][profile_key]
    queue = get_vibration_queue(profile_key)
    logs = donation_logs.get(profile_key, [])
    return render_template(
        "index.html",
        user=user,
        profile=profile,
        queue=queue,
        logs=logs,
        current_mode=mode,  # 👈 передаём в шаблон
    )


@app.route("/qrcode")
@login_required
def qrcode_page():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    qr_url = get_qr_code(profile_key)
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
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    q = vibration_queues.get(profile_key)
    return {"queue": list(q._queue) if q else []}

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/test_vibration", methods=["POST"])
@login_required
def test_vibration():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    threading.Thread(target=send_vibration_cloud, args=(profile_key, 1, 5)).start()
    return {"status": "ok", "message": "Вибрация отправлена ✅"}


@app.route("/stats")
@login_required
def stats():
    user = session.get("user")
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    stats_data = load_stats(profile_key)  # читаем stats_{profile_key}.json

    # считаем суммы за период
    total_income = sum(day["total"] * 0.7 for day in stats_data.values())

    # если Arina — берём проценты от Ирины
    if user == "Arina":
        irina_stats = load_stats(f"Irina_{mode}")
        archi_fee = sum(day["vibrations"] * 0.7 * 0.1 for day in irina_stats.values())
    else:
        archi_fee = sum(day["vibrations"] * 0.7 * 0.1 for day in stats_data.values())

    return render_template(
        "stats.html",
        user=user,
        stats=stats_data,
        total_income=round(total_income, 2),
        archi_fee=round(archi_fee, 2)
    )


@app.route("/stats_history")
@login_required
def stats_history():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    archive_file = f"stats_archive_{profile_key}.json"

    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except:
        archive = {}

    # фильтрация по датам
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    filtered = {}
    for day, data in archive.items():
        try:
            d = datetime.strptime(day, "%Y-%m-%d")
        except:
            continue
        if from_date and d < datetime.strptime(from_date, "%Y-%m-%d"):
            continue
        if to_date and d > datetime.strptime(to_date, "%Y-%m-%d"):
            continue
        filtered[day] = data

    # считаем суммы
    sum_vibr = sum(day["vibrations"] for day in filtered.values())
    sum_act = sum(day["actions"] for day in filtered.values())
    sum_other = sum(day["other"] for day in filtered.values())
    total_income = sum(day["total"] * 0.7 for day in filtered.values())

    # проценты Арине
    if user == "Arina":
        irina_archive_file = f"stats_archive_Irina_{mode}.json"
        try:
            with open(irina_archive_file, "r", encoding="utf-8") as f:
                irina_archive = json.load(f)
        except:
            irina_archive = {}
        archi_fee = sum(day["vibrations"] * 0.7 * 0.1 for day in irina_archive.values())
    else:
        archi_fee = sum(day["vibrations"] * 0.7 * 0.1 for day in filtered.values())

    return render_template(
        "stats_history.html",
        stats=filtered,
        user=user,
        total_income=round(total_income),
        archi_fee=round(archi_fee),
        sum_vibr=sum_vibr,
        sum_act=sum_act,
        sum_other=sum_other
    )


@app.route("/test_rule/<int:rule_index>", methods=["POST"])
@login_required
def test_rule(rule_index):
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    rules = load_rules(profile_key)

    if 0 <= rule_index < len(rules["rules"]):
        rule = rules["rules"][rule_index]
        strength = rule.get("strength", 1)
        duration = rule.get("duration", 5)

        print(
            f"🧪 [{profile_key}] Тест правила {rule_index}: сила={strength}, время={duration}"
        )
        send_vibration_cloud(profile_key, strength, duration)

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
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    with open(vip_file, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2, ensure_ascii=False)
    return redirect("/vip")


@app.route("/remove_member", methods=["POST"])
@login_required
def remove_member():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    user_id = request.form.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Нет user_id"}, 400

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
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

@app.route("/entries_data")
@login_required
def entries_data():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    profile = CONFIG["profiles"][profile_key]
    vip_file = profile["vip_file"]

    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    entries = []
    for user_id, info in vip_data.items():
        if info.get("_just_logged_in"):
            entries.append({
                "user_id": user_id,
                "name": info.get("name", "Аноним"),
                "last_login": info.get("_previous_login", info.get("last_login")),
                "visits": info.get("login_count", 0),
                "total_tips": info.get("total", 0),
                "notes": info.get("notes", "")
            })
            info["_just_logged_in"] = False

    # сохраняем изменения
    with open(vip_file, "w", encoding="utf-8") as f:
        json.dump(vip_data, f, indent=2, ensure_ascii=False)

    return {"entries": entries}


@app.route("/block_member", methods=["POST"])
@login_required
def block_member():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    user_id = request.form.get("user_id")
    if not user_id:
        return jsonify(status="error", message="Нет user_id"), 400

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        vip_data = {}

    if user_id in vip_data:
        vip_data[user_id]["blocked"] = True
        with open(vip_file, "w", encoding="utf-8") as f:
            json.dump(vip_data, f, indent=2, ensure_ascii=False)
        print(f"🚫 [{profile_key}] Мембер {user_id} заблокирован")
        return jsonify(status="ok", message="Мембер заблокирован")

    return jsonify(status="error", message="Мембер не найден"), 404


@app.route("/vip", methods=["GET", "POST"])
@login_required
def vip_page():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    vip_file = CONFIG["profiles"][profile_key]["vip_file"]

    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except:
        vip_data = {}

    if request.method == "POST" and "user_id" in request.form:
        user_id = request.form.get("user_id")
        if user_id in vip_data:
            vip_data[user_id]["name"] = request.form.get("name", "").strip()
            vip_data[user_id]["notes"] = request.form.get("notes", "").strip()
            with open(vip_file, "w", encoding="utf-8") as f:
                json.dump(vip_data, f, indent=2, ensure_ascii=False)

        # сохраняем параметры сортировки и поиска из формы
        sort_by = request.form.get("sort", "total")
        query = request.form.get("q", "")
        return redirect(url_for("vip_page", sort=sort_by, q=query))


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

    # 📋 Сортировка
    sort_by = request.args.get("sort", "total")  # total / login_count / last_login

    def parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.min

    if sort_by == "last_login":
        sorted_members = sorted(
            filtered.items(),
            key=lambda x: parse_date(x[1].get("last_login", "")),
            reverse=True
        )
    else:
        sorted_members = sorted(
            filtered.items(),
            key=lambda x: x[1].get(sort_by, 0),
            reverse=True
        )

    return render_template("vip.html", user=user, members=sorted_members, query=query)


@app.route("/update_name", methods=["POST"])
@login_required
def update_name():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    user_id = request.form.get("user_id")
    new_name = request.form.get("name")

    if not user_id or not new_name:
        return {"status": "error", "message": "Недостаточно данных"}, 400

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
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

@app.route("/vip_data")
@login_required
def vip_data():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    vip_file = CONFIG["profiles"][profile_key]["vip_file"]

    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        vip_data = {}

    return {"members": vip_data}


@app.route("/rules", methods=["GET", "POST"])
@login_required
def rules():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    rules_file = CONFIG["profiles"][profile_key]["rules_file"]

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
                "id": str(uuid.uuid4()),
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

    sorted_rules = sorted(rules_data["rules"], key=lambda r: r["min"])
    return render_template(
        "rules.html", rules=sorted_rules, default=rules_data["default"]
    )


@app.route("/logs")
@login_required
def logs_page():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    return render_template("logs.html", logs=donation_logs.get(profile_key, []))


@app.route("/set_mode", methods=["POST"])
@login_required
def set_mode():
    data = request.get_json(force=True)
    mode = data.get("mode")
    if mode in ("private", "public"):
        CURRENT_MODE["value"] = mode
        print(f"🔄 Режим переключен на {mode}")
        return {"status": "ok", "mode": mode}
    return {"status": "error", "message": "Неверный режим"}, 400


@app.route("/logs_data")
@login_required
def logs_data():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    return {"logs": donation_logs.get(profile_key, [])}


@app.route("/clear_logs", methods=["POST"])
@login_required
def clear_logs():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"

    # очищаем память
    donation_logs[profile_key] = []

    # очищаем файл
    log_file = f"donations_{profile_key}.log"
    open(log_file, "w", encoding="utf-8").close()

    return {"status": "ok", "message": "Логи очищены ✅"}


@app.route("/clear_queue", methods=["POST"])
@login_required
def clear_queue():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    q = vibration_queues.get(profile_key)
    if q:
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
            except:
                break
    return {"status": "ok", "message": "Очередь очищена ✅"}

@app.route("/close_period", methods=["POST"])
@login_required
def close_period():
    user = session["user"]
    mode = CURRENT_MODE["value"]
    profile_key = f"{user}_{mode}"
    stats_file = f"stats_{profile_key}.json"
    archive_file = f"stats_archive_{profile_key}.json"

    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except:
        stats = {}

    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except:
        archive = {}

    # добавляем в архив
    for day, values in stats.items():
        if day not in archive:
            archive[day] = values

    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)

    # очищаем текущую статистику
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2, ensure_ascii=False)

    return redirect("/stats")
@app.route("/obs_alert")
def obs_alert():
    return render_template("obs_alert.html")

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
            # раньше здесь был clear_processed_donations(), но он больше не нужен
            time.sleep(60)
    except KeyboardInterrupt:
        print("⏹ Остановка программы")


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=run_websocket, daemon=True).start()
    monitor_flag()