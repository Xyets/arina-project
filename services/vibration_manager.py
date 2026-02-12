# services/vibration_manager.py

import asyncio
from typing import Dict, Optional

# ГЛОБАЛЬНЫЕ структуры — единый источник истины
vibration_queues: Dict[str, asyncio.Queue] = {}
stop_events: Dict[str, asyncio.Event] = {}


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

def enqueue_vibration(profile_key: str, strength: int, duration: int) -> None:
    """
    Кладёт вибрацию в очередь.
    """
    ensure_profile(profile_key)
    q = vibration_queues[profile_key]

    try:
        q.put_nowait((strength, duration))
    except Exception as e:
        print(f"⚠️ Ошибка enqueue_vibration для {profile_key}: {e}")


# ---------------- ОСТАНОВКА ----------------

def stop_vibration(profile_key: str) -> None:
    """
    Ставит флаг остановки вибрации.
    vibration_worker увидит stop_events[profile_key].is_set()
    """
    ensure_profile(profile_key)
    stop_events[profile_key].set()
