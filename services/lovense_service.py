import json
import requests
import redis
from typing import Optional, Dict, Any
from config import CONFIG


redis_client = redis.StrictRedis(
    host=CONFIG.get("redis_host", "localhost"),
    port=CONFIG.get("redis_port", 6379),
    db=0
)


def _load_profile(profile_key: str) -> Optional[Dict[str, Any]]:
    """
    Загружает профиль из JSON-файла.
    """
    try:
        path = CONFIG["profiles"][profile_key]
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки профиля {profile_key}: {e}")
        return None


def _get_utoken_from_redis(uid: str) -> Optional[str]:
    raw = redis_client.hget("connected_users", uid)
    if not raw:
        return None

    try:
        user_data = json.loads(raw)
        return user_data.get("utoken")
    except Exception:
        return None


def send_vibration_cloud(profile_key: str, strength: int, duration: int) -> Optional[dict]:
    """
    Отправляет вибрацию в Lovense Cloud.
    """
    profile = _load_profile(profile_key)
    if not profile:
        return None

    uid = profile.get("uid")
    if not uid:
        print(f"❌ [{profile_key}] Нет uid в профиле")
        return None

    utoken = _get_utoken_from_redis(uid)
    if not utoken:
        print(f"❌ [{profile_key}] Игрушка не подключена или utoken отсутствует")
        return None

    url = "https://api.lovense.com/api/lan/v2/command"
    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": f"Vibrate:{strength}",
        "timeSec": duration,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ [{profile_key}] Ошибка Cloud-вибрации: {e}")
        return None


def stop_vibration_cloud(profile_key: str) -> Optional[dict]:
    """
    Останавливает вибрацию.
    """
    profile = _load_profile(profile_key)
    if not profile:
        return None

    uid = profile.get("uid")
    if not uid:
        print(f"❌ [{profile_key}] Нет uid в профиле")
        return None

    utoken = _get_utoken_from_redis(uid)
    if not utoken:
        print(f"❌ [{profile_key}] Игрушка не подключена или utoken отсутствует")
        return None

    url = "https://api.lovense.com/api/lan/v2/command"
    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": "Vibrate:0",
        "timeSec": 1,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ [{profile_key}] Ошибка остановки вибрации: {e}")
        return None
