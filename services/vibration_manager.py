import asyncio
from typing import Dict, Optional

# profile_key -> asyncio.Queue[(strength, duration)]
vibration_queues: Dict[str, asyncio.Queue] = {}

# profile_key -> asyncio.Event (сигнал остановки)
stop_events: Dict[str, asyncio.Event] = {}


def init_vibration_queues(profile_keys) -> None:
    """
    Создаёт (или гарантирует наличие) очереди вибраций и stop_event для каждого профиля.
    НЕ очищает существующие — только добавляет недостающие.
    """
    for key in profile_keys:
        if key not in vibration_queues:
            vibration_queues[key] = asyncio.Queue()
        if key not in stop_events:
            stop_events[key] = asyncio.Event()


def ensure_profile(profile_key: str) -> None:
    """
    Гарантирует, что для профиля есть очередь и stop_event.
    """
    if profile_key not in vibration_queues:
        vibration_queues[profile_key] = asyncio.Queue()
    if profile_key not in stop_events:
        stop_events[profile_key] = asyncio.Event()


def get_vibration_queue(profile_key: str) -> Optional[asyncio.Queue]:
    """Возвращает очередь вибраций для профиля (создаёт при необходимости)."""
    ensure_profile(profile_key)
    return vibration_queues.get(profile_key)


def stop_vibration(profile_key: str) -> None:
    """
    Ставит флаг остановки вибрации.
    vibration_worker увидит stop_events[profile_key].is_set()
    """
    ensure_profile(profile_key)
    stop_events[profile_key].set()


def enqueue_vibration(profile_key: str, strength: int, duration: int) -> None:
    """
    Кладёт вибрацию в очередь нужного профиля.
    """
    ensure_profile(profile_key)

    q = vibration_queues.get(profile_key)
    if not q:
        return

    try:
        q.put_nowait((strength, duration))
    except Exception as e:
        print(f"⚠️ Ошибка enqueue_vibration для {profile_key}: {e}")
