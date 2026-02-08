# services/vibration_manager.py

import json
from services.redis_client import redis_client

# profile_key -> asyncio.Event (создаётся в ws_app)
stop_events = {}


def ensure_stop_event(profile_key: str, event):
    """
    Регистрирует stop_event, созданный в ws_app.
    """
    stop_events[profile_key] = event


def enqueue_vibration(profile_key: str, strength: int, duration: int) -> None:
    """
    Кладёт задачу вибрации в Redis-очередь.
    """
    payload = {
        "strength": strength,
        "duration": duration
    }

    try:
        redis_client.lpush(
            f"vibration_queue:{profile_key}",
            json.dumps(payload)
        )
    except Exception as e:
        print(f"⚠️ Ошибка enqueue_vibration для {profile_key}: {e}")
