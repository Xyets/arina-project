import asyncio
import json
import websockets
import redis
from services.vip_service import update_vip
from services.logs_service import add_log

from config import CONFIG
from services.goal_service import load_goal

from services.vibration_manager import (
    init_vibration_queues,
    vibration_queues,
    stop_vibration,
    stop_events,          # ← ДОБАВИТЬ ЭТО
)


# ---------------- ГЛОБАЛЬНЫЕ СТРУКТУРЫ ----------------

CONNECTED_SOCKETS = set()
CLIENT_TYPES = {}          # ws -> "panel" / "obs"
CLIENT_PROFILES = {}       # ws -> profile_key (OBS)
CLIENT_USERS = {}          # ws -> user (panel)
CLIENT_MODES = {}

WS_EVENT_LOOP = None

redis_client = redis.StrictRedis(host="127.0.0.1", port=6379, db=0)


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
            CLIENT_USERS.pop(ws, None)


# ---------------- ВИБРАЦИИ ----------------
from services.vibration_manager import get_vibration_queue
async def vibration_worker(profile_key):
    q = get_vibration_queue(profile_key)

    from services.vibration_manager import stop_events
    from services.lovense_service import send_vibration_cloud, stop_vibration_cloud

    while True:
        strength, duration = await q.get()

        # Сбрасываем STOP перед новой вибрацией
        stop_events[profile_key].clear()

        # Запускаем вибрацию на duration секунд (как раньше)
        send_vibration_cloud(profile_key, strength, duration)

        # OBS-анимация
        msg = json.dumps({
            "vibration": {
                "strength": strength,
                "duration": duration,
                "target": profile_key
            }
        })
        for ws in list(CONNECTED_SOCKETS):
            try:
                await ws.send(msg)
            except:
                CONNECTED_SOCKETS.discard(ws)

        # Ждём duration секунд, но проверяем STOP
        for _ in range(duration):
            await asyncio.sleep(1)

            if stop_events[profile_key].is_set():
                stop_vibration_cloud(profile_key)

                # STOP в OBS
                stop_msg = json.dumps({
                    "stop": True,
                    "target": profile_key
                })
                for ws in list(CONNECTED_SOCKETS):
                    try:
                        await ws.send(stop_msg)
                    except:
                        CONNECTED_SOCKETS.discard(ws)

                break

        q.task_done()



# ---------------- REDIS LISTENER ----------------

async def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("obs_reactions")

    while True:
        msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if msg:
            try:
                data = json.loads(msg["data"].decode("utf-8"))
                profile_key = data.get("profile")
                ws_send(data, role="obs", profile_key=profile_key)
            except Exception:
                pass

        await asyncio.sleep(0.1)


# ---------------- ОСНОВНОЙ WS HANDLER ----------------

async def ws_handler(websocket):
    CONNECTED_SOCKETS.add(websocket)
    CLIENT_TYPES[websocket] = None

    try:
        async for message in websocket:
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
                    user = data.get("user")
                    mode = data.get("mode", "private")

                    CLIENT_USERS[websocket] = user
                    CLIENT_MODES[user] = mode  # сохраняем режим панели

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
                user = data.get("user")  # Arina / Irina

                mode = CLIENT_MODES.get(user, "private")
                profile_key = f"{user}_{mode}"

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

                user = data.get("user")
                name = (data.get("name") or "Аноним").strip()
                text = data.get("text", "")
                amount = float(data.get("amount") or 0)

                if not user or amount <= 0:
                    await websocket.send(json.dumps({"error": "invalid_donation"}))
                    continue

                mode = CLIENT_MODES.get(user, "private")
                profile_key = f"{user}_{mode}"

                from services.donation_service import handle_donation

                result = handle_donation(profile_key, name, amount, text)

                # если правило содержит вибрацию — шлём панели таймер
                rule = result.get("rule")
                if rule and rule.get("kind") == "vibration":
                    vib = rule

                # 🔥 ПРАВИЛЬНОЕ ОБНОВЛЕНИЕ ЦЕЛИ (как в goal_app)
                ws_send({
                    "goal_update": True,
                    "goal": result["goal"]
                }, role="panel")

                ws_send({"type": "refresh_logs"}, role="panel")
                continue

            # ---------- STOP ----------
            if msg_type == "stop":
                profile_key = data.get("profile_key")

                if not profile_key:
                    user = data.get("user")
                    mode = CLIENT_MODES.get(user, "private")
                    profile_key = f"{user}_{mode}"

                stop_vibration(profile_key)

                ws_send(
                    {"stop": True, "target": profile_key},
                    role="obs",
                    profile_key=profile_key
                )
                continue

            # ---------- SET MODE ----------
            if msg_type == "set_mode":
                user = data.get("user")
                mode = data.get("mode")

                CLIENT_MODES[user] = mode

                ws_send(
                    {"mode_update": mode, "user": user},
                    role="panel"
                )
                continue

            # ---------- VIP UPDATE ----------
            if msg_type == "vip_update":
                user = data.get("user")
                mode = CLIENT_MODES.get(user, "private")
                profile_key = f"{user}_{mode}"

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

                payload = {
                    "vibration": {
                        "strength": strength,
                        "duration": duration,
                        "target": profile_key
                    }
                }

                ws_send(payload, role="obs", profile_key=profile_key)
                continue

    finally:
        CONNECTED_SOCKETS.discard(websocket)
        CLIENT_TYPES.pop(websocket, None)
        CLIENT_PROFILES.pop(websocket, None)
        CLIENT_USERS.pop(websocket, None)


# ---------------- ЗАПУСК WS ----------------

async def ws_server():
    global WS_EVENT_LOOP
    WS_EVENT_LOOP = asyncio.get_running_loop()

    # Берём ключи профилей напрямую из CONFIG
    profile_keys = list(CONFIG["profiles"].keys())
    print("🔥 WS SERVER PROFILE KEYS:", profile_keys)

    # Инициализируем очереди вибраций для всех профилей
    init_vibration_queues(profile_keys)

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

