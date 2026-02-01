# services/vibration_manager.py

import asyncio
from typing import Dict, Optional

# profile_key -> asyncio.Queue[(strength, duration)]
vibration_queues: Dict[str, asyncio.Queue] = {}

# profile_key -> asyncio.Event (сигнал остановки)
stop_events: Dict[str, asyncio.Event] = {}


def init_vibration_queues(profile_keys) -> None:
    """
    Создаёт очередь вибраций и stop_event для каждого профиля.
    """
    global vibration_queues, stop_events

    vibration_queues = {key: asyncio.Queue() for key in profile_keys}
    stop_events = {key: asyncio.Event() for key in profile_keys}


def get_vibration_queue(profile_key: str) -> Optional[asyncio.Queue]:
    """Возвращает очередь вибраций для профиля."""
    return vibration_queues.get(profile_key)


def stop_vibration(profile_key: str) -> None:
    """
    Ставит флаг остановки вибрации.
    vibration_worker увидит stop_events[profile_key].is_set()
    """
    if profile_key in stop_events:
        stop_events[profile_key].set()


def enqueue_vibration(profile_key: str, strength: int, duration: int) -> None:
    """
    Кладёт вибрацию в очередь нужного профиля.
    ВАЖНО: НЕ сбрасываем stop_event здесь!
    Это делает vibration_worker перед началом новой вибрации.
    """
    q = vibration_queues.get(profile_key)
    if not q:
        return

    try:
        q.put_nowait((strength, duration))
    except Exception as e:
        print(f"⚠️ Ошибка enqueue_vibration для {profile_key}: {e}")
