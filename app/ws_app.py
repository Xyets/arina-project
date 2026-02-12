print("🔥🔥🔥 WS_APP.PY LOADED 🔥🔥🔥")
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO)

import asyncio
import json
import websockets

from config import CONFIG
from services.vip_service import update_vip
from services.logs_service import add_log
from services.lovense_service import send_vibration_cloud
from services.vibration_manager import vibration_queues, stop_events
from services.redis_client import redis_client


# ---------------- ГЛОБАЛЬНЫЕ СТРУКТУРЫ ----------------

CONNECTED_SOCKETS = set()
CLIENT_TYPES = {}          # ws -> "panel" / "obs"
CLIENT_PROFILES = {}       # ws -> profile_key
WS_EVENT_LOOP = None


# ---------------- УТИЛИТА ДЛЯ РАССЫЛКИ ----------------

def ws_send(data, role=None, profile_key=None):
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
    print(f"🔥 vibration_worker STARTED for {profile_key}")
    q = vibration_queues[profile_key]

    while True:
        try:
            # ждём следующую вибрацию
            strength, duration = await q.get()

            print(f"🔥 [{profile_key}] NEW vibration: strength={strength}, duration={duration}")
            ws_send({
                "queue_update": True,
                "queue": list(q._queue)
            }, role="panel", profile_key=profile_key)

            # STOP event reset
            if profile_key not in stop_events:
                stop_events[profile_key] = asyncio.Event()
            stop_events[profile_key].clear()

            # --- отправляем вибрацию в Lovense Cloud ---
            try:
                print(f"🚀 [{profile_key}] Sending vibration to Cloud...")
                await send_vibration_cloud(profile_key, strength, duration)
            except Exception as e:
                print(f"❌ [{profile_key}] Cloud vibration ERROR:", e)

            # --- отправляем на панель и OBS ---
            payload = {
                "vibration": {
                    "strength": strength,
                    "duration": duration,
                    "target": profile_key
                }
            }
            ws_send(payload, role="panel", profile_key=profile_key)
            ws_send(payload, role="obs", profile_key=profile_key)

            # --- таймер вибрации с возможностью STOP ---
            total_steps = duration * 10
            for _ in range(total_steps):
                await asyncio.sleep(0.1)

                if stop_events[profile_key].is_set():
                    print(f"🛑 [{profile_key}] STOP received, stopping vibration")
                    try:
                        await send_vibration_cloud(profile_key, 0, 0)
                    except Exception as e:
                        print(f"❌ [{profile_key}] Cloud STOP ERROR:", e)

                    ws_send({"stop": True, "target": profile_key}, role="obs", profile_key=profile_key)
                    break

        except Exception as e:
            print(f"⚠️ [{profile_key}] ERROR in vibration_worker:", e)

        finally:
            q.task_done()
            ws_send({
                "queue_update": True,
                "queue": list(q._queue)
            }, role="panel", profile_key=profile_key)



# ---------------- REDIS LISTENER ----------------

async def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("obs_reactions", "vibrations")
    print("🔥 Redis listener started")

    while True:
        msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if msg:
            try:
                raw = msg["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")

                data = json.loads(raw)

                # ---------- VIBRATIONS ----------
                if "strength" in data and "duration" in data and "profile_key" in data:
                    pk = data["profile_key"]
                    vibration_queues[pk].put_nowait((data["strength"], data["duration"]))
                    print(f"🔥 Redis vibration queued for {pk}: {data['strength']} / {data['duration']}")
                    continue

                # ---------- OBS REACTIONS ----------
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
                profile_key = data.get("profile_key")

                if role == "panel":
                    CLIENT_TYPES[websocket] = "panel"
                    CLIENT_PROFILES[websocket] = profile_key

                    # 🔥 Автоматически обновляем режим пользователя в Redis
                    try:
                        user, mode = profile_key.split("_")
                        redis_client.hset("user_modes", user, mode)
                    except Exception as e:
                        print("❌ Ошибка обновления режима:", e)

                    await websocket.send(json.dumps({"status": "hello_ok", "role": "panel"}))
                    continue

                if role == "obs":
                    CLIENT_TYPES[websocket] = "obs"
                    CLIENT_PROFILES[websocket] = profile_key
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
                user = data.get("user")  # "Arina" / "Irina"

                # определяем режим из Redis
                mode = redis_client.hget("user_modes", user)
                if isinstance(mode, bytes):
                    mode = mode.decode("utf-8")
                if mode not in ("private", "public"):
                    mode = "private"

                profile_key = f"{user}_{mode}"

                profile = update_vip(profile_key, viewer_id, name=viewer_name, event=event)

                if event == "login":
                    add_log(profile_key, f"🔵 LOGIN | {viewer_name} ({viewer_id})")
                elif event == "logout":
                    add_log(profile_key, f"🔴 LOGOUT | {viewer_name} ({viewer_id})")
                else:
                    add_log(profile_key, f"📥 EVENT | {event.upper()} | {viewer_name} ({viewer_id}) → {text}")

                ws_send({"type": "refresh_logs"}, role="panel", profile_key=profile_key)
                continue


            # ---------- DONATION ----------
            if msg_type == "donation":
                from services.donation_service import handle_donation

                # 1. Определяем пользователя
                user = data.get("user")  # "Arina" или "Irina"
                user_id = data.get("user_id")
                name = (data.get("name") or "Аноним").strip()
                text = data.get("text", "")
                amount = float(data.get("amount") or 0)

                # 2. Определяем режим пользователя из Redis
                mode = redis_client.hget("user_modes", user)
                if isinstance(mode, bytes):
                    mode = mode.decode("utf-8")

                if mode not in ("private", "public"):
                    mode = "private"

                # 3. Собираем profile_key автоматически
                profile_key = f"{user}_{mode}"

                # 4. Проверка корректности
                if not user_id or amount <= 0:
                    await websocket.send(json.dumps({"error": "invalid_donation"}))
                    continue

                # 5. Обработка доната
                result = handle_donation(profile_key, user_id, name, amount, text)

                # 6. Обновления панели
                ws_send({"vip_update": True, "user_id": user_id, "profile_key": profile_key})
                ws_send({"goal_update": True, "goal": result["goal"]}, role="panel", profile_key=profile_key)
                ws_send({"type": "refresh_logs"}, role="panel", profile_key=profile_key)

                continue


            # ---------- STOP ----------
            if msg_type == "stop":
                profile_key = data.get("profile_key")

                if profile_key not in stop_events:
                    stop_events[profile_key] = asyncio.Event()

                stop_events[profile_key].set()
                send_vibration_cloud(profile_key, 0, 0)

                ws_send({"stop": True, "target": profile_key}, role="obs", profile_key=profile_key)
                continue

            # ---------- ВИБРАЦИИ ОТ ПАНЕЛИ ----------
            if msg_type == "vibration":
                profile_key = data.get("profile_key")
                strength = data.get("strength")
                duration = data.get("duration")

                if not profile_key or strength is None or duration is None:
                    continue

                # Кладём задачу в очередь
                vibration_queues[profile_key].put_nowait((strength, duration))

                # Отправляем на фронт
                payload = {
                    "vibration": {
                        "strength": strength,
                        "duration": duration,
                        "target": profile_key
                    }
                }
                ws_send(payload, role="panel", profile_key=profile_key)
                ws_send(payload, role="obs", profile_key=profile_key)
                continue
            # ---------- CLEAR QUEUE ----------
            if msg_type == "clear_queue":
                profile_key = data.get("profile_key")
                if profile_key in vibration_queues:
                    vibration_queues[profile_key] = asyncio.Queue()

                ws_send({
                    "queue_update": True,
                    "queue": []
                }, role="panel", profile_key=profile_key)

                continue

    finally:
        CONNECTED_SOCKETS.discard(websocket)
        CLIENT_TYPES.pop(websocket, None)
        CLIENT_PROFILES.pop(websocket, None)


# ---------------- ЗАПУСК WS ----------------

async def ws_server():
    global WS_EVENT_LOOP
    WS_EVENT_LOOP = asyncio.get_running_loop()

    profile_keys = list(CONFIG["profiles"].keys())
    print("🔥 WS SERVER PROFILE KEYS:", profile_keys)
    # Инициализация очередей и STOP событий
    for key in profile_keys:
        vibration_queues[key] = asyncio.Queue()
        stop_events[key] = asyncio.Event()

    # Запуск фоновых задач
    asyncio.create_task(redis_listener())
    for key in profile_keys:
        asyncio.create_task(vibration_worker(key))

    server = await websockets.serve(ws_handler, "127.0.0.1", 8765)
    await server.wait_closed()


def run_websocket_server():
    asyncio.run(ws_server())


if __name__ == "__main__":
    run_websocket_server()
