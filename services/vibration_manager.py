# services/vibration_manager.py

import asyncio
from typing import Dict, Tuple, Optional

# profile_key -> asyncio.Queue[(strength, duration)]
vibration_queues: Dict[str, asyncio.Queue] = {}


def init_vibration_queues(profile_keys) -> None:
    """
    Создаёт очередь вибраций для каждого профиля.
    Вызывать ТОЛЬКО внутри того event loop, где работает WebSocket.
    """
    global vibration_queues
    vibration_queues = {
        key: asyncio.Queue() for key in profile_keys
    }


def get_vibration_queue(profile_key: str) -> Optional[asyncio.Queue]:
    """
    Возвращает очередь вибраций для профиля.
    """
    return vibration_queues.get(profile_key)


def enqueue_vibration(profile_key: str, strength: int, duration: int) -> None:
    """
    Кладёт вибрацию в очередь нужного профиля.
    Если очереди нет — тихо игнорируем (например, профиль не активен).
    """
    q = vibration_queues.get(profile_key)
    if q:
        try:
            q.put_nowait((strength, duration))
        except Exception as e:
            print(f"⚠️ Ошибка enqueue_vibration для {profile_key}: {e}")
