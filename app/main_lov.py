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
from app.audit import audit_event
from collections import deque
from app.stats_service import calculate_stats, get_stats
from werkzeug.utils import secure_filename
import redis # type: ignore
import glob
from app.goal_service import load_goal, save_goal


with open("config/config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

def get_current_mode():
    return session.get("mode", "private")

def cleanup_all_backups(base_dir=".", keep=2):
    """
    Удаляет старые .bak файлы во всём проекте.
    Оставляет только N последних для каждого оригинального файла.
    """
    # Ищем ВСЕ .bak файлы
    all_bak = glob.glob(os.path.join(base_dir, "**", "*.bak"), recursive=True)

    # Группируем по имени оригинального файла
    groups = {}
    for bak in all_bak:
        # Оригинальный файл = всё до первой точки даты
        original = bak.split(".")[0]
        groups.setdefault(original, []).append(bak)

    # Чистим каждую группу
    for original, files in groups.items():
        # сортируем по дате изменения
        files_sorted = sorted(files, key=os.path.getmtime)

        # если файлов больше чем нужно — удаляем старые
        if len(files_sorted) > keep:
            for old in files_sorted[:-keep]:
                try:
                    os.remove(old)
                    print(f"🗑 Удалён старый backup: {old}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить {old}: {e}")


app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "../templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "../static")
)
app.secret_key = CONFIG["secret_key"]
USERS = CONFIG["users"]

vibration_queues = {
    profile_key: asyncio.Queue() for profile_key in CONFIG["profiles"].keys()
}
CONNECTED_USERS = {}
USER_MODES = { "Arina": "private", "Irina": "private" }

def ws_send(data):
    message = json.dumps(data)

    # получаем event loop, который запустил run_websocket
    loop = asyncio.get_event_loop()

    for ws in list(CONNECTED_SOCKETS):
        try:
            asyncio.run_coroutine_threadsafe(ws.send(message), loop)
        except:
            CONNECTED_SOCKETS.discard(ws)


RULES_DIR = "data/rules"
WS_EVENT_LOOP = None
redis_client = redis.StrictRedis(host="127.0.0.1", port=6379, db=0)
# ---------------- LOVENSE ----------------

def daily_backup_cleanup():
    while True:
        try:
            print("🧹 Ежедневная очистка .bak файлов...")
            cleanup_all_backups("data")
            print("✔ Очистка завершена")
        except Exception as e:
            print(f"⚠ Ошибка очистки .bak: {e}")

        # ждать 24 часа
        time.sleep(24 * 60 * 60)


def handle_donation(profile_key, sender, amount, text):
    sender_name = sender or "Анонимно"
    user = profile_key.split("_")[0]

    decision = apply_rule(profile_key, amount, text)

    if decision and decision["kind"] == "action":
        add_log(
            profile_key,
            f"✅ [{user}] Донат | {sender_name} → {amount} 🎬 Действие: {decision['action_text']}",
        )
        update_stats(profile_key, "actions", amount)

    elif decision and decision["kind"] == "vibration":
        add_log(
            profile_key,
            f"✅ [{user}] Донат | {sender_name} → {amount} 🏰 Вибрация: сила={decision['strength']}, время={decision['duration']}",
        )
        update_stats(profile_key, "vibrations", amount)

    else:
        add_log(
            profile_key, f"✅ [{user}] Донат | {sender_name} → {amount} 🍀 Без действия"
        )
        update_stats(profile_key, "other", amount)

    update_donations_sum(profile_key, amount)

    mode = profile_key.split("_")[1] 
    audit_event( profile_key, mode,
        {"type": "donation", "amount": amount, "sender": sender_name, "text": text},
    )


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


def load_logs_from_file(profile_key):
    log_file = f"data/donations/donations_{profile_key}.log"
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
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"{ts} | {message}"

    log_file = f"data/donations/donations_{profile_key}.log"
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

    raw = redis_client.hget("connected_users", uid)
    if not raw:
        print(f"❌ [{profile_key}] Нет данных из callback — игрушка не подключена")
        return None
    user_data = json.loads(raw)

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

def stop_vibration_cloud(profile_key):
    profile = CONFIG["profiles"][profile_key]
    uid = profile["uid"]

    raw = redis_client.hget("connected_users", uid)
    if not raw:
        print(f"❌ [{profile_key}] Нет данных из callback — игрушка не подключена")
        return None
    user_data = json.loads(raw)

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
        "action": "Vibrate:0",
        "timeSec": 1
    }

    try:
        print(f"⛔ [{profile_key}] Остановка вибрации → {payload}")
        r = requests.post(url, json=payload, timeout=10)
        print(f"📥 [{profile_key}] Ответ Cloud API: {r.text}")
        return r.json()
    except Exception as e:
        print(f"❌ [{profile_key}] Ошибка остановки вибрации:", e)
        return None


@app.route("/lovense/callback", methods=["POST"])
def lovense_callback():
    data = request.json or request.form
    print("📩 Callback от Lovense:", data)

    uid = data.get("uid")
    if uid:
        payload = {
            "utoken": data.get("utoken"),
            "toys": data.get("toys", {}),
        }
        redis_client.hset("connected_users", uid, json.dumps(payload, ensure_ascii=False))
        print("🔐 CONNECTED_USERS (Redis) обновлён:", uid)
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

            msg = json.dumps(
                {
                    "vibration": {
                        "strength": strength,
                        "duration": duration,
                        "target": profile_key,  # ← совпадает с {{ user }} на фронте
                    }
                }
            )
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
            mode = profile_key.split("_")[1] 
            audit_event( profile_key, mode,
                {
                    "type": "rule",
                    "matched": "action" if action else "vibration",
                    "amount": amount,
                    "strength": rule.get("strength", 1),
                    "duration": rule.get("duration", 5),
                    "text": text,
                },
            )
            if action and action.strip():
                # ⚠️ здесь НЕ вызываем update_stats
                return {"kind": "action", "action_text": action.strip()}
            else:
                strength = rule.get("strength", 1)
                duration = rule.get("duration", 5)
                vibration_queues[profile_key].put_nowait((strength, duration))
                # ⚠️ здесь тоже НЕ вызываем update_stats
                return {"kind": "vibration", "strength": strength, "duration": duration}
    return None

def load_reaction_rules(profile_key):
    path = f"data/reactions/reactions_{profile_key}.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"rules": []}


def save_reaction_rules(profile_key, rules):
    path = f"data/reactions/reactions_{profile_key}.json"
    tmp_file = path + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, path)


def apply_reaction_rule(profile_key, amount):
    """
    Проверяет сумму доната против правил реакций.
    Если совпадает — возвращает событие для OBS.
    """
    rules = load_reaction_rules(profile_key)
    for rule in rules.get("rules", []):
        if rule["min_points"] <= amount <= rule["max_points"]:
            # формируем событие
            event = {
                "reaction": rule["id"],
                "profile": profile_key,
                "duration": rule.get("duration", 5),
                "image": rule.get("image")
            }
            return event
    return None


# ---------------- VIP ----------------

def update_vip(profile_key, user_id, name=None, amount=0, event=None):
    profile = CONFIG["profiles"][profile_key]
    vip_file = profile["vip_file"]

    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            vip_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"⚠️ Ошибка чтения {vip_file}, отмена обновления")
        return None

    if user_id in vip_data and vip_data[user_id].get("blocked"):
        print(f"🚫 [{profile_key}] Мембер {user_id} заблокирован — пропускаем")
        return vip_data.get(user_id)

    if user_id not in vip_data:
        vip_data[user_id] = {
            "name": name or "Аноним",
            "alias": "",
            "total": 0.0,
            "notes": "",
            "login_count": 0,
            "last_login": "",
            "_previous_login": "",
            "blocked": False,
            "_just_logged_in": True,
        }

    if name:
        current_name = vip_data[user_id].get("name", "")
        if not current_name or current_name == "Аноним":
            vip_data[user_id]["name"] = name

    if amount and amount > 0:
        mode = profile_key.split("_")[1] 
        audit_event( profile_key, mode,
            {"type": "vip_total_increment", "user_id": user_id, "amount": amount})
        vip_data[user_id]["total"] = float(vip_data[user_id].get("total", 0.0)) + float(amount)
        
    if event and event.lower() == "login":
        mode = profile_key.split("_")[1] 
        audit_event( profile_key, mode,
            {"type": "vip_login", "user_id": user_id, "name": name})
        vip_data[user_id]["login_count"] += 1
        old_login = vip_data[user_id].get("last_login")
        if old_login:
            vip_data[user_id]["_previous_login"] = old_login
        vip_data[user_id]["last_login"] = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        vip_data[user_id]["_just_logged_in"] = True

    # резервная копия с датой

    if os.path.exists(vip_file):
        backup_file = f"{vip_file}.{datetime.now().strftime('%Y-%m-%d')}.bak"
        shutil.copy(vip_file, backup_file)
        cleanup_all_backups("data")

    # атомарная запись с блокировкой
    tmp_file = vip_file + ".tmp"
    with LOCK:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(vip_data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, vip_file)

    return vip_data[user_id]

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


def calculate_stats(stats: dict, user: str, irina_stats: dict = None):
    results = {}
    sum_vibr = sum(float(data.get('vibrations', 0.0)) for data in stats.values())
    sum_act = sum(float(data.get('actions', 0.0)) for data in stats.values())
    sum_other = sum(float(data.get('other', 0.0)) for data in stats.values())
    sum_total = sum(float(data.get('total', 0.0)) for data in stats.values())
    sum_donations = sum(float(data.get('donations_sum', 0.0)) for data in stats.values())

    archi_fee = 0.0
    total_income = 0.0

    for day, data in stats.items():
        base_income = float(data.get('total', 0.0)) * 0.7
        if user == "Irina":
            archi = float(data.get('vibrations', 0.0)) * 0.7 * 0.1
            net_income = base_income - archi
            results[day] = {**data, "archi_fee": archi, "net_income": net_income}
            archi_fee += archi
            total_income += net_income
        else:
            net_income = base_income
            results[day] = {**data, "net_income": net_income}
            total_income += net_income

    if user == "Arina" and irina_stats:
        archi_fee = sum(float(d.get("vibrations", 0.0)) * 0.7 * 0.1 for d in irina_stats.values())

    summary = {
        "sum_vibr": sum_vibr,
        "sum_act": sum_act,
        "sum_other": sum_other,
        "sum_total": sum_total,
        "sum_donations": sum_donations,
        "archi_fee": archi_fee,
        "total_income": total_income
    }
    return results, summary


def try_extract_user_id_from_text(text):
    m_hex = re.search(r"\b([0-9a-f]{32})\b", text, re.IGNORECASE)
    if m_hex:
        return m_hex.group(1)
    m_nonopan = re.search(r"nonopan(\d{1,7})", text, re.IGNORECASE)
    if m_nonopan:
        return m_nonopan.group(1)
    return None


def calculate_archi_fee(stats_data):
    """
    Считает archi_fee по формуле vibrations * 0.7 * 0.1
    """
    return sum(day.get("vibrations", 0) * 0.7 * 0.1 for day in stats_data.values())


# --- список уже обработанных донатов ---
def load_stats(profile_key):
    stats_file = f"data/stats/stats_{profile_key}.json"
    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def build_stats_from_logs(profile_key):
    stats = {}
    log_file = f"data/donations/donations_{profile_key}.log"
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                date = line.split(" | ")[0].strip()[:10]
                if date not in stats:
                    stats[date] = {
                        "vibrations": 0,
                        "actions": 0,
                        "other": 0,
                        "total": 0,
                        "donations_sum": 0,
                    }

                # ищем сумму после "→"
                m = re.search(r"→\s*(\d+)", line)
                amount = int(m.group(1)) if m else 0

                if "🏰" in line:
                    stats[date]["vibrations"] += amount
                elif "🎬" in line:
                    stats[date]["actions"] += amount
                else:
                    stats[date]["other"] += amount

                stats[date]["total"] += amount
                stats[date]["donations_sum"] += amount
    except FileNotFoundError:
        print(f"⚠️ Лог-файл {log_file} не найден")
    except Exception as e:
        print(f"⚠️ Ошибка чтения {log_file}: {e}")
    return stats


RECENT_DONATIONS = deque(maxlen=500)  # хранит последние 500 donation_id


def update_stats(profile_key, category: str, amount: float = 0.0):
    stats_file = f"data/stats/stats_{profile_key}.json"
    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        stats = {}

    day = datetime.now().strftime("%Y-%m-%d")

    if day not in stats:
        stats[day] = {
            "vibrations": 0.0,
            "actions": 0.0,
            "other": 0.0,
            "total": 0.0,
            "donations_sum": 0.0,
        }

    # увеличиваем только категорию
    stats[day][category] = stats[day].get(category, 0.0) + float(amount)

    # пересчёт total как сумма категорий
    stats[day]["total"] = (
        stats[day]["vibrations"] + stats[day]["actions"] + stats[day]["other"]
    )

    tmp_file = stats_file + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, stats_file)


def update_donations_sum(profile_key, amount: float = 0.0):
    today = datetime.now().strftime("%Y-%m-%d")
    stats_file = f"data/stats/stats_{profile_key}.json"
    stats = load_stats(profile_key)

    if today not in stats:
        stats[today] = {
            "vibrations": 0.0,
            "actions": 0.0,
            "other": 0.0,
            "total": 0.0,
            "donations_sum": 0.0,
        }

    stats[today]["donations_sum"] += float(amount or 0.0)

    tmp_file = stats_file + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, stats_file)


def extract_strength(text):
    m = re.search(r"сила[:=]\s*(\d+)", text)
    return int(m.group(1)) if m else None


def extract_duration(text):
    m = re.search(r"время[:=]\s*(\d+)", text)
    return int(m.group(1)) if m else None

def update_goal(profile_key, amount):
    goal = load_goal(profile_key)
    goal["current"] += amount
    save_goal(profile_key, goal)

    # отправляем WS
    asyncio.create_task(ws_send({
        "goal_update": True,
        "goal": goal
    }))



async def ws_handler(websocket):
    global CURRENT_MODE

    print("🔌 WebSocket подключён")
    CONNECTED_SOCKETS.add(websocket)

    try:
        async for message in websocket:
            try:
                print("📩 Получено сообщение от WebSocket:", message)
                data = json.loads(message)

                # ---------------------------------------------------------
                # 🔄 1. Переключение режима (команда от панели)
                # ---------------------------------------------------------
                if data.get("type") == "set_mode":
                    user = data.get("user")
                    mode = data.get("mode")
                    if user in USER_MODES:
                        USER_MODES[user] = mode
                        print(f"🔄 {user} переключил режим на: {mode}")

                        await websocket.send(
                            json.dumps({"status": "ok", "mode": USER_MODES[user]})
                        )

                    else:
                        await websocket.send(json.dumps({"error": "invalid_mode"}))

                    continue
                if data.get("type") == "set_mode":
                    user = data.get("user")
                    mode = data.get("mode")
                    if user in USER_MODES:
                        USER_MODES[user] = mode
                        print(f"🔄 {user} переключил режим на: {mode}")

                        await websocket.send(
                            json.dumps({"status": "ok", "mode": USER_MODES[user]})
                        )
                        # 🔥 Рассылаем обновление режима всем клиентам
                        msg = json.dumps({
                            "mode_update": USER_MODES[user],
                            "user": user
                        })
                        for ws in list(CONNECTED_SOCKETS):
                            try:
                                await ws.send(msg)
                            except:
                                CONNECTED_SOCKETS.discard(ws)
                       
                # ---------------------------------------------------------
                # 🛑 1.1. Остановка вибрации (команда от панели)
                # ---------------------------------------------------------
                if data.get("type") == "stop":
                    user = data.get("user")
                    if user:
                        mode = USER_MODES.get(user, "private")
                        profile_key = f"{user}_{mode}"

                        msg = json.dumps({
                            "stop": True,
                            "target": profile_key
                        })

                        for ws in list(CONNECTED_SOCKETS):
                            try:
                                await ws.send(msg)
                            except:
                                CONNECTED_SOCKETS.discard(ws)

                    continue


                # ---------------------------------------------------------
                # 🔧 2. Общие данные
                # ---------------------------------------------------------
                user = data.get("user")
                if not user:
                    await websocket.send(json.dumps({"error": "no_profile"}))

                    continue

                # 🔥 Используем текущий режим, выбранный в панели
                mode = USER_MODES.get(user, "private") 
                profile_key = f"{user}_{mode}"

                if profile_key not in CONFIG.get("profiles", {}):
                    await websocket.send(json.dumps({"error": "profile_not_found", "profile": profile_key}))
                    continue

                text = data.get("text", "")
                name = (data.get("name") or "Аноним").strip()
                user_id = data.get("user_id")
                donation_id = data.get("donation_id")

                # ---------------------------------------------------------
                # 👤 3. События входа/выхода
                # ---------------------------------------------------------
                if "event" in data:
                    event = data["event"].lower()

                    profile = update_vip(profile_key, user_id, name=name, event=event)

                    if event == "login":
                        add_log(profile_key, f"🔵 LOGIN | {name} ({user_id})")
                    elif event == "logout":
                        add_log(profile_key, f"🔵 LOGOUT | {name} ({user_id})")
                    else:
                        add_log(
                            profile_key,
                            f"📥 Событие: {event.upper()} | {name} ({user_id}) → {text}",
                        )

                    # Рассылка обновления VIP
                    msg = json.dumps({
                        "vip_update": True,
                        "user_id": user_id,
                        "profile_key": profile_key,
                    })
                    for ws in list(CONNECTED_SOCKETS):
                        try:
                            await ws.send(msg)
                        except:
                            CONNECTED_SOCKETS.discard(ws)

                    # Отправляем данные о входе
                    if profile and profile.get("_just_logged_in"):
                        await websocket.send(json.dumps({
                            "entry": {
                                "user_id": user_id,
                                "name": profile["name"],
                                "visits": profile["login_count"],
                                "last_login": profile["_previous_login"],
                                "total_tips": profile["total"],
                                "notes": profile["notes"],
                            }
                        }))
                        profile["_just_logged_in"] = False

                    await websocket.send(json.dumps({"status": "event_ok", "event": event}))
                    continue

                # ---------------------------------------------------------
                # 💸 4. Донаты
                # ---------------------------------------------------------
                try:
                    amount = float(data.get("amount") or 0)
                except:
                    amount = 0.0

                if amount <= 0:
                    await websocket.send(json.dumps({"info": "no_donation"}))
                    continue

                # Защита от повторов
                if donation_id:
                    if donation_id in RECENT_DONATIONS:
                        print(f"⚠️ Повтор доната {donation_id} — пропускаем")
                        await websocket.send(json.dumps({"info": "duplicate_donation"}))
                        continue
                    RECENT_DONATIONS.append(donation_id)

                # Запись доната
                handle_donation(profile_key, name, amount, text)

                # Обновление VIP
                if user_id:
                    profile = update_vip(profile_key, user_id, name=name, amount=amount)

                    msg = json.dumps({
                        "vip_update": True,
                        "user_id": user_id,
                        "profile_key": profile_key,
                    })
                    for ws in list(CONNECTED_SOCKETS):
                        try:
                            await ws.send(msg)
                        except:
                            CONNECTED_SOCKETS.discard(ws)

                # Реакции
                reaction_event = apply_reaction_rule(profile_key, amount)
                if reaction_event:
                    msg = json.dumps(reaction_event)
                    for ws in list(CONNECTED_SOCKETS):
                        try:
                            await ws.send(msg)
                        except:
                            CONNECTED_SOCKETS.discard(ws)

                await websocket.send(json.dumps({"status": "donation_ok"}))
            except Exception as e:
                print("⚠️ Ошибка обработки:", e)
                await websocket.send(json.dumps({"error": "processing_error"}))

    finally:
        CONNECTED_SOCKETS.discard(websocket)
        print("🔌 WebSocket отключён")


async def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("obs_reactions")
    print("🔔 Redis listener запущен")

    loop = asyncio.get_event_loop()
    while True:
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if message:
            data = message["data"].decode("utf-8")
            print(f"📩 Получено из Redis: {data}")
            for ws in list(CONNECTED_SOCKETS):
                try:
                    await ws.send(data)
                except:
                    CONNECTED_SOCKETS.discard(ws)
        await asyncio.sleep(0.1)


async def ws_server():
    for profile_key in CONFIG["profiles"]:
        asyncio.create_task(vibration_worker(profile_key))

    await asyncio.gather(
        websockets.serve(ws_handler, "0.0.0.0", 8765),
        redis_listener()
    )

# ---------------- Flask Routes ----------------
@app.route("/")
@login_required
def index():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"

    profile = CONFIG["profiles"][profile_key]
    queue = get_vibration_queue(profile_key)
    logs = load_logs_from_file(profile_key)
    goal = load_goal(profile_key)

    return render_template(
        "index.html",
        user=user,
        profile=profile,
        queue=queue,
        logs=logs,
        current_mode=mode,
        mode=mode,
        goal=goal
    )



@app.route("/qrcode")
@login_required
def qrcode_page():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
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
    mode = USER_MODES.get(user, "private")
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
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"

    def safe_vibration():
        try:
            send_vibration_cloud(profile_key, 1, 5)
        except Exception as e:
            print(f"⚠️ Ошибка тестовой вибрации: {e}")

    threading.Thread(target=safe_vibration).start()

    return {"status": "ok", "message": "Вибрация отправлена ✅"}


@app.route("/stats")
@login_required
def stats():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    stats_data = load_stats(profile_key)
    irina_stats = load_stats(f"Irina_{mode}") if user == "Arina" else None
    results, summary = calculate_stats(stats_data, user=user, irina_stats=irina_stats)
    return render_template("stats.html", user=user, results=results, summary=summary)


@app.route("/stats_history")
@login_required
def stats_history():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    archive_file = f"data/stats/stats_archive_{profile_key}.json"

    # Загружаем архив периодов
    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        archive = {"periods": []}

    # Фильтрация по датам (если нужно)
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    if from_date and to_date:
        filtered_periods = []
        for p in archive.get("periods", []):
            if p["start"] >= from_date and p["end"] <= to_date:
                filtered_periods.append(p)
        archive = {"periods": filtered_periods}

    return render_template("stats_history.html", user=user, archive=archive)

@app.route("/reactions", methods=["GET", "POST"])
@login_required
def reactions_page():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"

    rules = load_reaction_rules(profile_key)
    STATIC_REACTIONS_DIR = "/var/www/arina-project/static/reactions"

    if request.method == "POST":
        if "add_reaction_rule" in request.form:
            new_rule = {
                "id": str(uuid.uuid4()),
                "min_points": int(request.form["min_points"]),
                "max_points": int(request.form["max_points"]),
                "duration": int(request.form["duration"]),
                "image": None
            }
            file = request.files.get("image")
            if file and file.filename:
                safe_name = secure_filename(file.filename)
                filename = f"{profile_key}_{uuid.uuid4()}_{safe_name}"
                file.save(os.path.join(STATIC_REACTIONS_DIR, filename))
                new_rule["image"] = f"reactions/{filename}"  # путь относительно /static/

            rules["rules"].append(new_rule)
            save_reaction_rules(profile_key, rules)

        elif "delete_reaction_rule" in request.form:
            rule_id = request.form["delete_reaction_rule"]
            rules["rules"] = [r for r in rules["rules"] if r["id"] != rule_id]
            save_reaction_rules(profile_key, rules)

        elif "edit_reaction_rule" in request.form:
            rule_id = request.form["edit_reaction_rule"]
            for r in rules["rules"]:
                if r["id"] == rule_id:
                    r["min_points"] = int(request.form["min_points"])
                    r["max_points"] = int(request.form["max_points"])
                    r["duration"] = int(request.form["duration"])
                    file = request.files.get("image")
                    if file and file.filename:
                        safe_name = secure_filename(file.filename)
                        filename = f"{profile_key}_{uuid.uuid4()}_{safe_name}"
                        file.save(os.path.join(STATIC_REACTIONS_DIR, filename))
                        r["image"] = f"reactions/{filename}"  # ← исправлено

            save_reaction_rules(profile_key, rules)

    profile = CONFIG["profiles"].get(profile_key, {"uname": profile_key})
    return render_template("reactions.html", profile=profile, reactions=rules, profile_key=profile_key)


@app.route("/obs_reactions/<profile_key>")
def obs_reactions(profile_key):
    return render_template("obs_reactions.html", profile_key=profile_key)


@app.route("/test_reaction", methods=["POST"])
def test_reaction():
    data = request.get_json()
    rule_id = data.get("rule_id")
    profile_key = data.get("profile_key")

    rules = load_reaction_rules(profile_key)
    rule = next((r for r in rules["rules"] if r["id"] == rule_id), None)
    if not rule:
        return jsonify({"status": "error", "message": "Правило не найдено"}), 404

    event = {
        "reaction": rule["id"],
        "profile": profile_key,
        "duration": rule.get("duration", 5),
        "image": rule.get("image")
    }
    msg = json.dumps(event)

    # публикуем в Redis
    redis_client.publish("obs_reactions", msg)

    print(f"📡 Тест-евент отправлен в Redis: {msg}")
    return jsonify({"status": "ok"})


@app.route("/donations_data")
@login_required
def donations_data():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    logs = donation_logs.get(profile_key, [])
    donations = []
    for entry in logs:
        if "→" in entry:
            m = re.search(r"→\s*([\d\.]+)", entry)
            amount = float(m.group(1)) if m else 0.0
            donations.append({"entry": entry, "amount": amount})
    return {"donations": donations[-50:]}



@app.route("/test_rule/<int:rule_index>", methods=["POST"])
@login_required
def test_rule(rule_index):
    user = session["user"]
    mode = USER_MODES.get(user, "private")
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
        # проверка подписи от GitHub
        signature = request.headers.get("X-Hub-Signature-256")
        secret = CONFIG["webhook_secret"].encode()
        body = request.data
        expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature or "", expected):
            print("❌ Неверный секрет")
            return "Forbidden", 403

        data = request.get_json(silent=True)
        print("📩 Пришёл webhook:", data)

        # обновление проекта и зависимостей
        result = subprocess.run(
            [
                "bash",
                "-lc",
                "cd /root/arina-project && "
                "git pull && "
                "source venv/bin/activate && "
                "pip install -r requirements.txt && "
                "sudo systemctl restart arina.service && "
                "sudo systemctl restart arina-ws.service"
            ],
            capture_output=True,
            text=True
        )

        print("🔧 Результат обновления:\n", result.stdout)
        if result.stderr:
            print("⚠️ Ошибки:\n", result.stderr)

        return "✅ Hook обработан", 200

    except Exception as e:
        print("⚠️ Ошибка hook:", e)
        return "Internal Server Error", 500


@app.route("/Success", methods=["GET"])
def success_page():
    return "✅ Игрушка успешно подключена!", 200


@app.route("/Error", methods=["GET"])
def error_page():
    return "❌ Ошибка подключения!", 200


import threading, shutil, os, json
from datetime import datetime
from flask import request, jsonify, redirect, url_for, render_template, session

LOCK = threading.Lock()

def load_vip_file(vip_file: str) -> dict:
    """Безопасная загрузка VIP-файла"""
    try:
        with open(vip_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}

def save_vip_file(vip_file: str, vip_data: dict):
    """Атомарная запись VIP-файла с защитой от повреждений"""
    if not isinstance(vip_data, dict):
        print("❌ vip_data не словарь — отмена записи")
        return

    # Создаём резервную копию только один раз в день
    if os.path.exists(vip_file):
        backup_file = f"{vip_file}.{datetime.now().strftime('%Y-%m-%d')}.bak"
        if not os.path.exists(backup_file):
            shutil.copy(vip_file, backup_file)

    tmp_file = vip_file + ".tmp"

    with LOCK:
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(vip_data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_file, vip_file)

        except Exception as e:
            print("❌ Ошибка записи VIP-файла:", e)
            if os.path.exists(tmp_file):
                os.remove(tmp_file)



@app.route("/remove_member", methods=["POST"])
@login_required
def remove_member():
    user = session["user"]; mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    user_id = request.form.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Нет user_id"}, 400

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    vip_data = load_vip_file(vip_file)
    if not vip_data:
        return {"status": "error", "message": "Ошибка чтения VIP‑файла"}, 500

    if user_id in vip_data:
        del vip_data[user_id]
        save_vip_file(vip_file, vip_data)
        return {"status": "ok", "message": "Мембер удалён"}
    return {"status": "error", "message": "Мембер не найден"}, 404


@app.route("/entries_data")
@login_required
def entries_data():
    user = session["user"]; mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    vip_file = CONFIG["profiles"][profile_key]["vip_file"]

    vip_data = load_vip_file(vip_file)
    if not vip_data:
        return {"entries": []}

    entries = []
    for user_id, info in vip_data.items():
        if info.get("_just_logged_in"):
            entries.append({
                "user_id": user_id,
                "name": info.get("name", "Аноним"),
                "last_login": info.get("_previous_login", info.get("last_login")),
                "visits": info.get("login_count", 0),
                "total_tips": int(info.get("total", 0)),
                "notes": info.get("notes", ""),
            })
            info["_just_logged_in"] = False

    save_vip_file(vip_file, vip_data)
    return {"entries": entries}


@app.route("/vip", methods=["GET", "POST"])
@login_required
def vip_page():
    user = session["user"]; mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    vip_file = CONFIG["profiles"][profile_key]["vip_file"]

    vip_data = load_vip_file(vip_file)

    if request.method == "POST" and "user_id" in request.form:
        user_id = request.form.get("user_id")
        if user_id in vip_data:
            vip_data[user_id]["name"] = request.form.get("name", "").strip()
            vip_data[user_id]["notes"] = request.form.get("notes", "").strip()
            save_vip_file(vip_file, vip_data)

        sort_by = request.form.get("sort", "total")
        query = request.form.get("q", "")
        return redirect(url_for("vip_page", sort=sort_by, q=query))

    query = request.args.get("q", "").strip().lower()
    filtered = {
        uid: info for uid, info in vip_data.items()
        if not query
        or query in uid.lower()
        or query in info.get("name", "").lower()
        or query in info.get("notes", "").lower()
    }

    sort_by = request.args.get("sort", "total")

    def parse_date(s: str):
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return datetime.min

    if sort_by == "last_login":
        sorted_members = sorted(
            filtered.items(),
            key=lambda x: parse_date(x[1].get("last_login", "")),
            reverse=True,
        )
    else:
        sorted_members = sorted(
            filtered.items(), key=lambda x: x[1].get(sort_by, 0), reverse=True
        )

    return render_template("vip.html", user=user, members=sorted_members, query=query)


@app.route("/update_name", methods=["POST"])
@login_required
def update_name():
    user = session["user"]; mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    user_id = request.form.get("user_id")
    new_name = request.form.get("name")

    if not user_id or not new_name:
        return {"status": "error", "message": "Недостаточно данных"}, 400

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    vip_data = load_vip_file(vip_file)
    if not vip_data:
        return {"status": "error", "message": "Ошибка чтения VIP‑файла"}, 500

    if user_id not in vip_data:
        return {"status": "error", "message": "Мембер не найден"}, 404

    vip_data[user_id]["name"] = new_name.strip()
    save_vip_file(vip_file, vip_data)
    return {"status": "ok"}


@app.route("/vip_data")
@login_required
def vip_data():
    user = session["user"]; mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    vip_file = CONFIG["profiles"][profile_key]["vip_file"]

    vip_data = load_vip_file(vip_file)
    return {"members": vip_data}


@app.route("/rules", methods=["GET", "POST"])
@login_required
def rules():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
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
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    logs = load_logs_from_file(profile_key)   # ← читаем файл заново
    return render_template("logs.html", logs=logs)


@app.route("/set_mode", methods=["POST"])
@login_required
def set_mode():
    data = request.get_json(force=True)
    mode = data.get("mode")

    if mode in ("private", "public"):
        session["mode"] = mode
        print(f"🔄 Режим переключен на {mode}")
        return {"status": "ok", "mode": mode}

    return {"status": "error", "message": "Неверный режим"}, 400



@app.route("/logs_data")
@login_required
def logs_data():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    logs = load_logs_from_file(profile_key)   # ← читаем файл заново
    return jsonify({"logs": logs})


@app.route("/logs_data_stats")
@login_required
def logs_data_stats():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    logs = load_logs_from_file(profile_key)   # ← читаем файл заново
    formatted = []

    for line in logs:
        ts = line.split(" | ")[0]  # дата и время
        m = re.search(r"→\s*([\d\.]+)", line)
        amount = float(m.group(1)) if m else 0.0

        if "🏰" in line:
            type = "vibration"
        elif "🎬" in line:
            type = "action"
        elif "🍀" in line:
            type = "plain"
        elif "LOGIN" in line or "LOGOUT" in line or "🔵" in line:
            type = "loginout"
        else:
            type = "other"

        if "→" in line:
            formatted.append({"ts_local": ts, "amount": round(amount, 2), "type": type})

    return {"logs": formatted}


@app.route("/clear_logs", methods=["POST"])
@login_required
def clear_logs():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"

    # очищаем память
    donation_logs[profile_key] = []

    # атомарная очистка файла
    log_file = f"data/donations/donations_{profile_key}.log"
    tmp_file = log_file + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write("")  # пустой файл
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, log_file)
    except Exception as e:
        print(f"⚠️ Ошибка очистки логов {log_file}: {e}")

    return {"status": "ok", "message": "Логи очищены ✅"}


@app.route("/clear_queue", methods=["POST"])
@login_required
def clear_queue():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"
    q = vibration_queues.get(profile_key)
    if q:
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
            except Exception:
                break
    return {"status": "ok", "message": "Очередь очищена ✅"}


@app.route("/close_period", methods=["POST"])
@login_required
def close_period():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"

    stats_file = f"data/stats/stats_{profile_key}.json"
    archive_file = f"data/stats/stats_archive_{profile_key}.json"

    # Загружаем текущую статистику (дни)
    stats = load_stats(profile_key)

    if not stats:
        return redirect(url_for("stats_history"))

    # Загружаем архив периодов
    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        archive = {"periods": []}

    # Определяем границы периода
    days_sorted = sorted(stats.keys())
    start_day = days_sorted[0]
    end_day = days_sorted[-1]

    # Считаем суммы
    total_income = 0
    total_vibrations = 0
    total_actions = 0
    total_other = 0
    total_archi_fee = 0

    for day, data in stats.items():
        total_income += data.get("net_income", 0)
        total_vibrations += data.get("vibrations", 0)
        total_actions += data.get("actions", 0)
        total_other += data.get("other", 0)
        total_archi_fee += data.get("archi_fee", 0)

    # Создаём новый период
    new_period = {
        "id": len(archive["periods"]) + 1,
        "start": start_day,
        "end": end_day,
        "total_income": total_income,
        "vibrations": total_vibrations,
        "actions": total_actions,
        "other": total_other,
        "archi_fee": total_archi_fee,
        "days": stats
    }

    # Добавляем в архив
    archive["periods"].append(new_period)

    # Сохраняем архив
    tmp = archive_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, archive_file)

    # Удаляем текущую статистику
    try:
        os.remove(stats_file)
    except FileNotFoundError:
        pass

    return redirect(url_for("stats_history"))


@app.route("/stop_vibration", methods=["POST"])
@login_required
def stop_vibration():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"

    result = stop_vibration_cloud(profile_key)
    return {"status": "ok" if result else "error"}



@app.route("/obs_alert_arina")
def obs_alert_arina():
    return render_template("obs_alert_arina.html")

@app.route("/obs_alert_irina")
def obs_alert_irina():
    return render_template("obs_alert_irina.html")

@app.route("/goal_data")
@login_required
def goal_data():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"

    goal = load_goal(profile_key)
    return goal

@app.route("/goal_new", methods=["POST"])
@login_required
def goal_new():
    user = session["user"]
    mode = USER_MODES.get(user, "private")
    profile_key = f"{user}_{mode}"

    title = request.form.get("title", "")
    target = int(request.form.get("target", 0))

    goal = {"title": title, "target": target, "current": 0}
    save_goal(profile_key, goal)

    asyncio.create_task(ws_send({
        "goal_update": True,
        "goal": goal
    }))

    return {"status": "ok"}



# ---------------- ЗАПУСК ----------------
def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False)


def run_websocket():
    global WS_EVENT_LOOP
    loop = asyncio.new_event_loop()
    WS_EVENT_LOOP = loop
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(ws_server())
        loop.run_forever()
    except Exception as e:
        print(f"⚠️ Ошибка WebSocket-сервера: {e}")


def monitor_flag():
    print("🚀 Программа запущена. Ожидание донатов через WebSocket...")
    try:
        while True:
            print("⏳ Сервер работает, ожидание продолжается...")
            time.sleep(60)
    except KeyboardInterrupt:
        print("⏹ Остановка программы")

# --- запуск ежедневной очистки .bak ---
cleanup_thread = threading.Thread(target=daily_backup_cleanup, daemon=True) 
cleanup_thread.start()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=run_websocket, daemon=True).start()
    monitor_flag()