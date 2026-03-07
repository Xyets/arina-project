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
from services.lovense_service import send_vibration_cloud_async

from services.vibration_manager import vibration_queues, stop_events
from services.redis_client import redis_client
from services.vibration_manager import init_vibration_queues

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

            for i in range(duration * 10):
                await asyncio.sleep(0.1)

                if stop_events[profile_key].is_set():
                    print(f"🛑 [{profile_key}] STOP RECEIVED DURING WAIT at {i*0.1:.1f}s")

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
        msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0)

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

                    # 🔥 ДОБАВЬ ЭТО
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

        await asyncio.sleep(0.01)



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

                    # сохраняем режим пользователя
                    try:
                        user, mode = profile_key.split("_")
                        redis_client.hset("user_modes", user, mode)
                    except Exception as e:
                        print("❌ Ошибка обновления режима:", e)

                    # отправляем актуальную очередь (только будущие вибрации)
                    if profile_key in vibration_queues:
                        ws_send({
                            "queue_update": True,
                            "queue": list(vibration_queues[profile_key]._queue)
                        }, role="panel", profile_key=profile_key)

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
                user = data.get("user")

                mode = redis_client.hget("user_modes", user)
                if isinstance(mode, bytes):
                    mode = mode.decode("utf-8")
                if mode not in ("private", "public"):
                    mode = "private"

                profile_key = f"{user}_{mode}"

                # 🔥 вызываем update_vip ТОЛЬКО ОДИН РАЗ
                profile = update_vip(profile_key, viewer_id, name=viewer_name, event=event)

                # обновляем VIP
                ws_send({
                    "vip_update": True,
                    "user_id": viewer_id,
                    "profile_key": profile_key
                }, role="panel", profile_key=profile_key)

                # popup только при login
                if event == "login":
                    ws_send({
                        "entry": {
                            "name": viewer_name,
                            "visits": profile["login_count"],
                            "total_tips": profile["total"],
                            "notes": profile.get("notes", "")
                        }
                    }, role="panel", profile_key=profile_key)

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
                    continue

                result = handle_donation(profile_key, user_id, name, amount, text)

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

                loop = asyncio.get_running_loop()
                await send_vibration_cloud_async(profile_key, 0, 0)


                ws_send({"stop": True, "target": profile_key}, role="panel", profile_key=profile_key)
                ws_send({"stop": True, "target": profile_key}, role="obs", profile_key=profile_key)

                # ❗ очередь НЕ обновляем — это важно
                continue

            # ---------- ВИБРАЦИИ ОТ ПАНЕЛИ ----------
            if msg_type == "vibration":
                profile_key = data.get("profile_key")
                strength = data.get("strength")
                duration = data.get("duration")

                if not profile_key or strength is None or duration is None:
                    continue

                # добавляем в очередь
                vibration_queues[profile_key].put_nowait((strength, duration))

                # 🔥 обновляем очередь (показываем будущие вибрации)
                ws_send({
                    "queue_update": True,
                    "queue": list(vibration_queues[profile_key]._queue)
                }, role="panel", profile_key=profile_key)

                # визуальное уведомление
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

                continue

            # ---------- CLEAR QUEUE ----------
            if msg_type == "clear_queue":
                profile_key = data.get("profile_key")

                if profile_key in vibration_queues:
                    q = vibration_queues[profile_key]

                    # очищаем ТЕКУЩУЮ очередь, не создавая новую
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
                continue

            # ---------- GET QUEUE ----------
            if msg_type == "get_queue":
                profile_key = data.get("profile_key")

                if profile_key in vibration_queues:
                    q = list(vibration_queues[profile_key]._queue)
                else:
                    q = []

                ws_send({
                    "queue_update": True,
                    "queue": q
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