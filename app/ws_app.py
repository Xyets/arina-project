print("🔥🔥🔥 WS_APP.PY LOADED 🔥🔥🔥")
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
logging.basicConfig(level=logging.INFO)

import asyncio
import json
import websockets
import aiohttp
from config import CONFIG
from services.vip_service import update_vip
from services.logs_service import add_log
from services.lovense_service import send_vibration_cloud_async

from services.vibration_manager import vibration_queues, stop_events
from services.redis_client import redis_client
from services.vibration_manager import init_vibration_queues

# ---------------- ГЛОБАЛЬНЫЕ СТРУКТУРЫ ----------------

CONNECTED_SOCKETS = set()
CLIENT_TYPES = {}          # ws -> "panel" / "obs"
CLIENT_PROFILES = {}       # ws -> profile_key
WS_EVENT_LOOP = None

MAX_QUEUE_SIZE = 50  # максимум вибраций в очереди на профиль


def safe_enqueue_vibration(profile_key, strength, duration):
    """
    Добавляет вибрацию в очередь с ограничением размера.
    Если очередь переполнена — удаляем самый старый элемент.
    """
    if profile_key not in vibration_queues:
        print(f"⚠ safe_enqueue_vibration: unknown profile_key {profile_key}")
        return

    q = vibration_queues[profile_key]

    # если очередь слишком большая — удаляем старые элементы
    while q.qsize() >= MAX_QUEUE_SIZE:
        try:
            q.get_nowait()
            q.task_done()
        except Exception:
            break

    q.put_nowait((strength, duration))

# ---------------- УТИЛИТА ДЛЯ РАССЫЛКИ ----------------

def ws_send(data, role=None, profile_key=None):
    """
    Безопасная отправка сообщений всем подходящим клиентам.
    - фильтрация по роли и профилю
    - проверка закрытых сокетов
    - аккуратная очистка мёртвых соединений
    """
    if WS_EVENT_LOOP is None:
        print("⚠ ws_send: WS_EVENT_LOOP is None, message skipped:", data)
        return

    message = json.dumps(data)
    dead_sockets = []

    for ws in list(CONNECTED_SOCKETS):
        # фильтрация по роли
        if role and CLIENT_TYPES.get(ws) != role:
            continue

        # фильтрация по профилю
        if profile_key and CLIENT_PROFILES.get(ws) != profile_key:
            continue

        # если сокет уже закрыт — помечаем на удаление
        try:
            if not ws.open:
                dead_sockets.append(ws)
                continue
        except Exception:
            # если объект не имеет .open — считаем его мёртвым
            dead_sockets.append(ws)
            continue
        try:
            future = asyncio.run_coroutine_threadsafe(ws.send(message), WS_EVENT_LOOP)
            # можно добавить timeout, если нужно:
            # future.result(timeout=1)
        except Exception as e:
            print("❌ ws_send error:", e)
            dead_sockets.append(ws)

    # очистка мёртвых сокетов
    for ws in dead_sockets:
        CONNECTED_SOCKETS.discard(ws)
        CLIENT_TYPES.pop(ws, None)
        CLIENT_PROFILES.pop(ws, None)



# ---------------- ВИБРАЦИИ ----------------

async def vibration_worker(profile_key):
    print(f"🔥 WORKER STARTED for {profile_key}")

    from services.vibration_manager import vibration_queues, stop_events
    from services.lovense_service import start_vibration_cloud_async, stop_vibration_cloud_async

    q = vibration_queues[profile_key]

    while True:
        try:
            print(f"⏳ [{profile_key}] WAITING FOR NEXT VIBRATION…")
            strength, duration = await q.get()
            print(f"🚀 [{profile_key}] START NEW VIBRATION: strength={strength}, duration={duration}")

            # обновляем очередь
            ws_send({"queue_update": True, "queue": list(q._queue)}, role="panel", profile_key=profile_key)

            # сбрасываем стоп
            stop_events[profile_key].clear()
            print(f"🔄 [{profile_key}] stop_event CLEARED")

            # запускаем вибрацию
            print(f"📤 [{profile_key}] SENDING START COMMAND TO LOVENSE (fire-and-forget)…")
            asyncio.create_task(start_vibration_cloud_async(profile_key, strength, duration))
            print(f"📥 [{profile_key}] START COMMAND DISPATCHED")


            # уведомления
            ws_send({"vibration": {"strength": strength, "duration": duration, "target": profile_key}},
                    role="panel", profile_key=profile_key)
            ws_send({"vibration": {"strength": strength, "duration": duration, "target": profile_key}},
                    role="obs", profile_key=profile_key)

            # ждём duration или STOP
            print(f"⏳ [{profile_key}] WAITING {duration}s OR STOP…")
            stopped = False

            # ждём либо истечение времени, либо stop_event
            total_time = duration
            step = 0.1
            elapsed = 0.0

            while elapsed < total_time:
                await asyncio.sleep(step)
                elapsed += step

                if stop_events[profile_key].is_set():
                    print(f"🛑 [{profile_key}] STOP RECEIVED DURING WAIT at {elapsed:.1f}s")

                    print(f"📤 [{profile_key}] SENDING STOP COMMAND TO LOVENSE…")
                    await stop_vibration_cloud_async(profile_key)
                    print(f"📥 [{profile_key}] STOP COMMAND SENT")

                    ws_send({"stop": True, "target": profile_key}, role="panel", profile_key=profile_key)
                    ws_send({"stop": True, "target": profile_key}, role="obs", profile_key=profile_key)

                    stopped = True
                    break


            if not stopped:
                print(f"⏳ [{profile_key}] NATURAL END OF VIBRATION — SENDING STOP")
                await stop_vibration_cloud_async(profile_key)
                print(f"📥 [{profile_key}] NATURAL STOP SENT")

                ws_send({"vibration_finished": True, "target": profile_key}, role="obs", profile_key=profile_key)

            print(f"✅ [{profile_key}] VIBRATION COMPLETE — MOVING TO NEXT")

        except Exception as e:
            print(f"❌ [{profile_key}] ERROR IN WORKER:", e)

        finally:
            q.task_done()

# ---------------- REDIS LISTENER ----------------

async def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("obs_reactions", "vibrations")
    print("🔥 Redis listener started")

    while True:
        try:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        except Exception as e:
            print("❌ Redis pubsub error:", e)
            await asyncio.sleep(0.5)
            continue

        if msg:
            try:
                raw = msg["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")

                data = json.loads(raw)

                # ---------- VIBRATIONS ----------
                if "strength" in data and "duration" in data and "profile_key" in data:
                    pk = data["profile_key"]
                    if pk not in vibration_queues:
                        print(f"⚠ Redis: unknown profile_key {pk}, skipping vibration")
                    else:
                        safe_enqueue_vibration(pk, data["strength"], data["duration"])
                        print(f"🔥 Redis vibration queued for {pk}: {data['strength']} / {data['duration']}")

                        ws_send({
                            "queue_update": True,
                            "queue": list(vibration_queues[pk]._queue)
                        }, role="panel", profile_key=pk)

                    continue

                # ---------- OBS REACTIONS ----------
                profile_key = data.get("profile")
                ws_send(data, role="obs", profile_key=profile_key)

            except Exception as e:
                print("❌ Redis parse error:", e)

        # чуть меньше частота опроса
        await asyncio.sleep(0.05)


async def handle_ping(websocket):
    await websocket.send(json.dumps({"type": "pong"}))

async def handle_hello(websocket, data):
    role = data.get("role")
    profile_key = data.get("profile_key")

    if role == "panel":
        CLIENT_TYPES[websocket] = "panel"
        CLIENT_PROFILES[websocket] = profile_key

        try:
            user, mode = profile_key.split("_")
            redis_client.hset("user_modes", user, mode)
        except Exception as e:
            print("❌ Ошибка обновления режима:", e)

        if profile_key in vibration_queues:
            ws_send({
                "queue_update": True,
                "queue": list(vibration_queues[profile_key]._queue)
            }, role="panel", profile_key=profile_key)

        await websocket.send(json.dumps({"status": "hello_ok", "role": "panel"}))
        return

    if role == "obs":
        CLIENT_TYPES[websocket] = "obs"
        CLIENT_PROFILES[websocket] = profile_key
        await websocket.send(json.dumps({"status": "hello_ok", "role": "obs"}))
        return

    await websocket.send(json.dumps({"error": "unknown_role"}))

async def handle_viewer_event(websocket, data):
    event = data["event"].lower()
    viewer_id = data.get("user_id")
    viewer_name = data.get("name", "Анонимно")
    text = data.get("text", "")
    user = data.get("user")

    mode = redis_client.hget("user_modes", user)
    if isinstance(mode, bytes):
        mode = mode.decode("utf-8")
    if mode not in ("private", "public"):
        mode = "private"

    profile_key = f"{user}_{mode}"

    profile = update_vip(profile_key, viewer_id, name=viewer_name, event=event)

    ws_send({
        "vip_update": True,
        "user_id": viewer_id,
        "profile_key": profile_key
    }, role="panel", profile_key=profile_key)

    if event == "login":
        ws_send({
            "entry": {
                "name": viewer_name,
                "visits": profile["login_count"],
                "total_tips": profile["total"],
                "notes": profile.get("notes", "")
            }
        }, role="panel", profile_key=profile_key)

        # --- Расширенный лог ---
        name = profile.get("name", viewer_name)
        notes = profile.get("notes", "").strip() or "нет"
        total = profile.get("total", 0)
        login_count = profile.get("login_count", 0)
        prev_login = profile.get("_previous_login", "нет данных")

        log_message = (
            f"🔵 LOGIN | {name} | "
            f"📝 {notes} | "
            f"💗 {total} | "
            f"Предыдущий вход: {prev_login} | "
            f"Входов: {login_count}"
        )

        add_log(profile_key, log_message)


    elif event == "logout":
        add_log(profile_key, f"🔴 LOGOUT | {viewer_name} ({viewer_id})")

    else:
        add_log(profile_key, f"📥 EVENT | {event.upper()} | {viewer_name} ({viewer_id}) → {text}")

    ws_send({"type": "refresh_logs"}, role="panel", profile_key=profile_key)

async def handle_donation_event(websocket, data):
    from services.donation_service import handle_donation

    user = data.get("user")
    user_id = data.get("user_id")
    name = (data.get("name") or "Аноним").strip()
    text = data.get("text", "")
    amount = float(data.get("amount") or 0)

    mode = redis_client.hget("user_modes", user)
    if isinstance(mode, bytes):
        mode = mode.decode("utf-8")
    if mode not in ("private", "public"):
        mode = "private"

    profile_key = f"{user}_{mode}"

    if not user_id or amount <= 0:
        await websocket.send(json.dumps({"error": "invalid_donation"}))
        return

    result = handle_donation(profile_key, user_id, name, amount, text)

    ws_send({"vip_update": True, "user_id": user_id, "profile_key": profile_key})
    ws_send({"goal_update": True, "goal": result["goal"]}, role="panel", profile_key=profile_key)
    ws_send({"type": "refresh_logs"}, role="panel", profile_key=profile_key)

async def handle_stop(websocket, data):
    profile_key = data.get("profile_key")

    if profile_key not in stop_events:
        stop_events[profile_key] = asyncio.Event()

    stop_events[profile_key].set()

    await send_vibration_cloud_async(profile_key, 0, 0)

    ws_send({"stop": True, "target": profile_key}, role="panel", profile_key=profile_key)
    ws_send({"stop": True, "target": profile_key}, role="obs", profile_key=profile_key)

async def handle_vibration(websocket, data):
    profile_key = data.get("profile_key")
    strength = data.get("strength")
    duration = data.get("duration")

    if not profile_key or strength is None or duration is None:
        return

    safe_enqueue_vibration(profile_key, strength, duration)

    ws_send({
        "queue_update": True,
        "queue": list(vibration_queues[profile_key]._queue)
    }, role="panel", profile_key=profile_key)

    ws_send({
        "vibration": {
            "strength": strength,
            "duration": duration,
            "target": profile_key
        }
    }, role="panel", profile_key=profile_key)

    ws_send({
        "vibration": {
            "strength": strength,
            "duration": duration,
            "target": profile_key
        }
    }, role="obs", profile_key=profile_key)

async def handle_clear_queue(websocket, data):
    profile_key = data.get("profile_key")

    if profile_key in vibration_queues:
        q = vibration_queues[profile_key]
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
            except:
                break

    ws_send({
        "queue_update": True,
        "queue": []
    }, role="panel", profile_key=profile_key)

async def handle_get_queue(websocket, data):
    profile_key = data.get("profile_key")

    if profile_key in vibration_queues:
        q = list(vibration_queues[profile_key]._queue)
    else:
        q = []

    ws_send({
        "queue_update": True,
        "queue": q
    }, role="panel", profile_key=profile_key)

async def handle_wheel_result(websocket, data):
    profile_key = data.get("profile")
    action = data.get("action")

    # Логи
    if action.startswith("vibration:"):
        add_log(profile_key, f"🏰 Вибрация (колесо): {action}")
    else:
        add_log(profile_key, f"🎬 Действие (колесо): {action}")

    # Вибрация
    if action.startswith("vibration:"):
        try:
            _, strength, duration = action.split(":")
            strength = int(strength)
            duration = int(duration)

            safe_enqueue_vibration(profile_key, strength, duration)

            ws_send({
                "queue_update": True,
                "queue": list(vibration_queues[profile_key]._queue)
            }, role="panel", profile_key=profile_key)

        except Exception as e:
            print("❌ Ошибка обработки вибрации колеса:", e)

    # OBS реакция
    elif action.startswith("action:"):
        custom = action.replace("action:", "")

        ws_send({
            "reaction": {
                "image": custom,
                "duration": 5
            },
            "profile": profile_key
        }, role="obs", profile_key=profile_key)

    # Повторная попытка
    elif action == "wheel:retry":
        ws_send({
            "type": "wheel_spin_retry",
            "profile": profile_key
        }, role="obs", profile_key=profile_key)

    # Обновить логи
    ws_send({"type": "refresh_logs"}, role="panel", profile_key=profile_key)


# ---------------- ОСНОВНОЙ WS HANDLER ----------------

async def ws_handler(websocket):
    CONNECTED_SOCKETS.add(websocket)
    CLIENT_TYPES[websocket] = None

    try:
        async for message in websocket:
            print("📩 WS received:", message)

            # JSON парсинг
            try:
                data = json.loads(message)
            except Exception:
                print("⚠ Невозможно распарсить JSON:", message)
                continue

            # Определяем тип сообщения
            msg_type = data.get("type")

            # Донаты приходят без type
            if msg_type is None and "amount" in data:
                msg_type = "donation"

            # ---------- РОУТЕР СООБЩЕНИЙ ----------
            if msg_type == "ping":
                await handle_ping(websocket)
                continue

            if msg_type == "hello":
                await handle_hello(websocket, data)
                continue

            if "event" in data:
                await handle_viewer_event(websocket, data)
                continue

            if msg_type == "donation":
                await handle_donation_event(websocket, data)
                continue

            if msg_type == "stop":
                await handle_stop(websocket, data)
                continue

            if msg_type == "vibration":
                await handle_vibration(websocket, data)
                continue

            if msg_type == "clear_queue":
                await handle_clear_queue(websocket, data)
                continue

            if msg_type == "get_queue":
                await handle_get_queue(websocket, data)
                continue

            if msg_type == "wheel_result":
                await handle_wheel_result(websocket, data)
                continue

            # Если тип неизвестен
            print("⚠ Unknown WS message type:", msg_type)

    finally:
        # Удаляем сокет при отключении
        CONNECTED_SOCKETS.discard(websocket)
        CLIENT_TYPES.pop(websocket, None)
        CLIENT_PROFILES.pop(websocket, None)


# ---------------- ЗАПУСК WS ----------------

async def ws_server():
    global WS_EVENT_LOOP
    WS_EVENT_LOOP = asyncio.get_running_loop()

    from services.database import get_connection

    def get_all_profile_keys():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT profile_key FROM profiles")
        rows = cur.fetchall()
        conn.close()
        return [r["profile_key"] for r in rows]

    # 👉 ВОТ ЭТА СТРОКА БЫЛА ОТСУТСТВУЮЩЕЙ
    profile_keys = get_all_profile_keys()

    print("🔥 WS SERVER PROFILE KEYS:", profile_keys)

    # Инициализация очередей и STOP событий
    init_vibration_queues(profile_keys)

    # Запуск фоновых задач
    asyncio.create_task(redis_listener())

    for key in profile_keys:
        print("🚀 STARTING WORKER FOR", key)
        asyncio.create_task(vibration_worker(key))

    server = await websockets.serve(ws_handler, "127.0.0.1", 8765)
    await server.wait_closed()


def run_websocket_server():
    asyncio.run(ws_server())


if __name__ == "__main__":
    run_websocket_server()

