# services/vibration_manager.py

from asyncio import Queue
from config import CONFIG

# ---------------- ВИБРАЦИОННЫЕ ОЧЕРЕДИ ----------------

# Очереди вибраций для каждого профиля
vibration_queues = {
    key: Queue()
    for key in CONFIG["profiles"].keys()
}

# ---------------- STOP EVENTS ----------------

# События остановки вибрации для каждого профиля
stop_events = {
    key: None
    for key in CONFIG["profiles"].keys()
}

def ensure_stop_event(profile_key: str, event):
    """
    Регистрирует stop_event, созданный в ws_app.
    """
    stop_events[profile_key] = event
