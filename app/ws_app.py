import logging
logging.basicConfig(level=logging.INFO)
import asyncio
import json
import websockets
from services.vip_service import update_vip
from services.logs_service import add_log

from config import CONFIG
from services.vibration_manager import stop_events
from services.lovense_service import send_vibration_cloud



# ---------------- ГЛОБАЛЬНЫЕ СТРУКТУРЫ ----------------

CONNECTED_SOCKETS = set()
CLIENT_TYPES = {}          # ws -> "panel" / "obs"
CLIENT_PROFILES = {}       # ws -> profile_key (OBS)
      # ws -> user (panel)


WS_EVENT_LOOP = None

from services.redis_client import redis_client



# ---------------- УТИЛИТА ДЛЯ РАССЫЛКИ ----------------

def ws_send(data, role=None, profile_key=None):
    """
    role="panel"  → отправить только панели
    role="obs"    → отправить только OBS
    profile_key   → отправить только OBS конкретного профиля
    """
    message = json.dumps(data)

    for ws in list(CONNECTED_SOCKETS):
        try:
            if role and CLIENT_TYPES.get(ws) != role:
                continue

            if profile_key and CLIENT_PROFILES.get(ws) != profile_key:
                continue

            asyncio.run_coroutine_threadsafe(ws.send(message), WS_EVENT_LOOP)

        except Exception:
            CONNECTED_SOCKETS.discard(ws)
            CLIENT_TYPES.pop(ws, None)
            CLIENT_PROFILES.pop(ws, None)


# ---------------- ВИБРАЦИИ ----------------

async def vibration_worker(profile_key):
    from services.lovense_service import send_vibration_cloud

    loop = asyncio.get_running_loop()
    queue_name = f"vibration_queue:{profile_key}"

    while True:
        # ждём задачу из Redis
        raw = await loop.run_in_executor(None, redis_client.brpop, queue_name)
        task = json.loads(raw[1])

        strength = task["strength"]
        duration = task["duration"]

        if profile_key not in stop_events: 
            stop_events[profile_key] = asyncio.Event() 
        stop_events[profile_key].clear()

        # запускаем вибрацию
        send_vibration_cloud(profile_key, strength, duration)

        # отправляем в OBS и панель
        payload = {
            "vibration": {
                "strength": strength,
                "duration": duration,
                "target": profile_key
            }
        }
        ws_send(payload, role="obs", profile_key=profile_key)
        ws_send(payload, role="panel")

        # таймер с проверкой STOP каждые 100 мс
        for _ in range(duration * 10):
            await asyncio.sleep(0.1)
            if stop_events[profile_key].is_set():
                send_vibration_cloud(profile_key, 0, 0)
                ws_send({"stop": True, "target": profile_key}, role="obs", profile_key=profile_key)
                break



# ---------------- REDIS LISTENER ----------------

async def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("obs_reactions")
    print("🔥 Redis listener started")

    while True:
        msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if msg:
            print("📩 Redis raw message:", msg)

            try:
                raw = msg["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")

                data = json.loads(raw)
                print("📩 Redis parsed:", data)

                profile_key = data.get("profile")
                ws_send(data, role="obs", profile_key=profile_key)

            except Exception as e:
                print("❌ Redis parse error:", e)

        await asyncio.sleep(0.1)


# ---------------- ОСНОВНОЙ WS HANDLER ----------------

async def ws_handler(websocket):
    CONNECTED_SOCKETS.add(websocket)
    CLIENT_TYPES[websocket] = None

    try:
        async for message in websocket:
            print("📩 WS received:", message)
            try:
                data = json.loads(message)
            except Exception:
                continue

            msg_type = data.get("type")

            if msg_type is None and "amount" in data:
                msg_type = "donation"

            # ---------- PING ----------
            if msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))
                continue

            # ---------- HELLO ----------
            if msg_type == "hello":
                role = data.get("role")
                
                if role == "panel":
                    CLIENT_TYPES[websocket] = "panel"
                    profile_key = data.get("profile_key")
                    CLIENT_PROFILES[websocket] = profile_key
                    await websocket.send(json.dumps({"status": "hello_ok", "role": "panel"}))
                    continue


                if role == "obs":
                    CLIENT_TYPES[websocket] = "obs"
                    CLIENT_PROFILES[websocket] = data.get("profile_key")
                    await websocket.send(json.dumps({"status": "hello_ok", "role": "obs"}))
                    continue

                await websocket.send(json.dumps({"error": "unknown_role"}))
                continue

            # ---------- VIEWER LOGIN / LOGOUT ----------
            if "event" in data:
                event = data["event"].lower()
                viewer_id = data.get("user_id")
                viewer_name = data.get("name", "Анонимно")
                text = data.get("text", "")
                profile_key = data.get("profile_key")


                profile = update_vip(profile_key, viewer_id, name=viewer_name, event=event)

                if event == "login":
                    add_log(profile_key, f"🔵 LOGIN | {viewer_name} ({viewer_id})")
                elif event == "logout":
                    add_log(profile_key, f"🔴 LOGOUT | {viewer_name} ({viewer_id})")
                else:
                    add_log(profile_key, f"📥 EVENT | {event.upper()} | {viewer_name} ({viewer_id}) → {text}")

                ws_send({
                    "entry": {
                        "user_id": viewer_id,
                        "name": viewer_name,
                        "visits": profile.get("login_count", 1),
                        "last_login": profile.get("_previous_login"),
                        "total_tips": profile.get("total", 0),
                        "notes": profile.get("notes", "")
                    }
                }, role="panel")

                ws_send({"type": "refresh_logs"}, role="panel")
                continue

            # ---------- DONATION ----------
            if msg_type == "donation":
                print("🔥 DONATION RECEIVED:", data)

                profile_key = data.get("profile_key")
                user_id = data.get("user_id")  # ← настоящий уникальный ID
                name = (data.get("name") or "Аноним").strip()
                text = data.get("text", "")
                amount = float(data.get("amount") or 0)

                if not profile_key or not user_id or amount <= 0:
                    await websocket.send(json.dumps({"error": "invalid_donation"}))
                    continue


                from services.donation_service import handle_donation

                # передаём user_id первым аргументом
                result = handle_donation(profile_key, user_id, name, amount, text)
                profile = update_vip(profile_key, user_id, name=name, amount=amount)

                ws_send({
                    "vip_update": True,
                    "user_id": user_id,
                    "profile_key": profile_key,
                })

                ws_send({
                    "goal_update": True,
                    "goal": result["goal"]
                }, role="panel")

                ws_send({"type": "refresh_logs"}, role="panel")
                continue


            # ---------- STOP ----------
            if msg_type == "stop":
                profile_key = data.get("profile_key")


                if profile_key not in stop_events:
                    stop_events[profile_key] = asyncio.Event()

                stop_events[profile_key].set()

                send_vibration_cloud(profile_key, 0, 0)

                ws_send(
                    {"stop": True, "target": profile_key},
                    role="obs",
                    profile_key=profile_key
                )



            # ---------- VIP UPDATE ----------
            if msg_type == "vip_update":
                profile_key = data.get("profile_key")
                data["profile_key"] = profile_key
                ws_send(data, role="panel")
                continue

            # ---------- GOAL UPDATE ----------
            if msg_type == "goal_update":
                ws_send(data, role="panel")
                continue

            # ---------- ВИБРАЦИИ ОТ ПАНЕЛИ ----------
            if msg_type == "vibration":
                profile_key = data.get("profile_key")
                strength = data.get("strength")
                duration = data.get("duration")

                if not profile_key or strength is None or duration is None:
                    continue

                # КЛАДЁМ В REDIS ОЧЕРЕДЬ
                redis_client.lpush(
                    f"vibration_queue:{profile_key}",
                    json.dumps({"strength": strength, "duration": duration})
                )

                # Отправляем панель/OBS
                payload = {
                    "vibration": {
                        "strength": strength,
                        "duration": duration,
                        "target": profile_key
                    }
                }
                ws_send(payload, role="panel")
                ws_send(payload, role="obs", profile_key=profile_key)
                continue

    finally:
        CONNECTED_SOCKETS.discard(websocket)
        CLIENT_TYPES.pop(websocket, None)
        CLIENT_PROFILES.pop(websocket, None)


# ---------------- ЗАПУСК WS ----------------

async def ws_server():
    global WS_EVENT_LOOP
    WS_EVENT_LOOP = asyncio.get_running_loop()

    # Берём ключи профилей напрямую из CONFIG
    profile_keys = list(CONFIG["profiles"].keys())
    print("🔥 WS SERVER PROFILE KEYS:", profile_keys)

    # Создаём stop_events для всех профилей из CONFIG
    global stop_events
    stop_events = {key: asyncio.Event() for key in profile_keys}


    # Запускаем фоновые задачи
    asyncio.create_task(redis_listener())
    for key in profile_keys:
        asyncio.create_task(vibration_worker(key))

    # Запускаем WebSocket-сервер
    server = await websockets.serve(ws_handler, "127.0.0.1", 8765)
    await server.wait_closed()


def run_websocket_server():
    asyncio.run(ws_server())
if __name__ == "__main__":
    run_websocket_server()



