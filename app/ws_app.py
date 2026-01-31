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
    get_vibration_queue,
)

# ---------------- ГЛОБАЛЬНЫЕ СТРУКТУРЫ ----------------

CONNECTED_SOCKETS = set()
CLIENT_TYPES = {}          # ws -> "panel" / "obs"
CLIENT_PROFILES = {}       # ws -> profile_key (OBS)
CLIENT_USERS = {}          # ws -> user (panel)

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

async def vibration_worker(profile_key):
    q = get_vibration_queue(profile_key)
    if not q:
        return

    while True:
        strength, duration = await q.get()

        ws_send(
            {
                "vibration": {
                    "strength": strength,
                    "duration": duration,
                    "target": profile_key
                }
            },
            role="obs",
            profile_key=profile_key
        )

        await asyncio.sleep(duration)
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
                    CLIENT_USERS[websocket] = data.get("user")
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
                user_id = data.get("user_id")
                name = data.get("name", "Анонимно")
                text = data.get("text", "")

                # VIP обновление
                profile = update_vip(profile_key, user_id, name=name, event=event)

                # Логирование
                if event == "login":
                    add_log(profile_key, f"🔵 LOGIN | {name} ({user_id})")
                elif event == "logout":
                    add_log(profile_key, f"🔴 LOGOUT | {name} ({user_id})")
                else:
                    add_log(profile_key, f"📥 EVENT | {event.upper()} | {name} ({user_id}) → {text}")

                # Обновление панели
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

                mode = redis_client.hget("user_modes", user)
                mode = mode.decode() if mode else "private"
                profile_key = f"{user}_{mode}"

                from services.donation_service import handle_donation
                result = handle_donation(profile_key, name, amount, text)

                # обновление цели
                ws_send({"goal_update": True, "goal": result["goal"]}, role="panel")

                # 🔥 главное изменение — панель сама обновит лог
                ws_send({"type": "refresh_logs"}, role="panel")

                # если было правило — панель сама увидит его в JSON
                continue

            # ---------- STOP ----------
            if msg_type == "stop":
                user = data.get("user")
                mode = data.get("mode", "private")
                profile_key = f"{user}_{mode}"

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

                ws_send(
                    {"mode_update": mode, "user": user},
                    role="panel"
                )
                continue

            # ---------- VIP UPDATE ----------
            if msg_type == "vip_update":
                user = data.get("user")

                mode = redis_client.hget("user_modes", user)
                mode = mode.decode() if mode else "private"
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

                ws_send(
                    {
                        "vibration": {
                            "strength": strength,
                            "duration": duration,
                            "target": profile_key
                        }
                    },
                    role="obs",
                    profile_key=profile_key
                )
                continue

    finally:
        CONNECTED_SOCKETS.discard(websocket)
        CLIENT_TYPES.pop(websocket, None)
        CLIENT_PROFILES.pop(websocket, None)
        CLIENT_USERS.pop(websocket, None)


# ---------------- ЗАПУСК WS ----------------

async def ws_server(profile_keys):
    global WS_EVENT_LOOP
    WS_EVENT_LOOP = asyncio.get_running_loop()

    init_vibration_queues(profile_keys)

    asyncio.create_task(redis_listener())
    for key in profile_keys:
        asyncio.create_task(vibration_worker(key))

    server = await websockets.serve(ws_handler, "127.0.0.1", 8765)
    await server.wait_closed()


def run_websocket_server(profile_keys):
    asyncio.run(ws_server(profile_keys))
