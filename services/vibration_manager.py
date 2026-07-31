# services/vibration_manager.py

import asyncio
from typing import Dict

# ГЛОБАЛЬНЫЕ структуры
vibration_queues: Dict[str, asyncio.Queue] = {}
stop_events: Dict[str, asyncio.Event] = {}

MAX_QUEUE_SIZE = 50  # максимум вибраций в очереди


# ---------------- ВСПОМОГАТЕЛЬНЫЕ ----------------

def ensure_profile(profile_key: str) -> None:
    """
    Гарантирует, что для профиля есть очередь и stop_event.
    """
    if profile_key not in vibration_queues:
        vibration_queues[profile_key] = asyncio.Queue()

    if profile_key not in stop_events:
        stop_events[profile_key] = asyncio.Event()


def init_vibration_queues(profile_keys) -> None:
    """
    Инициализация всех профилей при старте ws_app.
    """
    for key in profile_keys:
        ensure_profile(key)


def get_vibration_queue(profile_key: str) -> asyncio.Queue:
    """
    Возвращает очередь вибраций (создаёт при необходимости).
    """
    ensure_profile(profile_key)
    return vibration_queues[profile_key]


# ---------------- ОЧЕРЕДЬ ВИБРАЦИЙ ----------------

def safe_enqueue(profile_key: str, strength: int, duration: int) -> None:
    """
    Безопасное добавление вибрации в очередь с ограничением размера.
    """
    ensure_profile(profile_key)
    q = vibration_queues[profile_key]

    # ограничение размера очереди
    while q.qsize() >= MAX_QUEUE_SIZE:
        try:
            q.get_nowait()
            q.task_done()
        except Exception:
            break

    q.put_nowait((strength, duration))


def clear_queue(profile_key: str) -> None:
    """
    Полностью очищает очередь вибраций.
    """
    ensure_profile(profile_key)
    q = vibration_queues[profile_key]

    while not q.empty():
        try:
            q.get_nowait()
            q.task_done()
        except Exception:
            break


# ---------------- ОСТАНОВКА ----------------

def stop_vibration(profile_key: str) -> None:
    """
    Ставит флаг остановки вибрации.
    vibration_worker увидит stop_events[profile_key].is_set()
    """
    ensure_profile(profile_key)
    stop_events[profile_key].set()


def clear_stop_flag(profile_key: str) -> None:
    """
    Сбрасывает stop_event перед новой вибрацией.
    """
    ensure_profile(profile_key)
    stop_events[profile_key].clear()
