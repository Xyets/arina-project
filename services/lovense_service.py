import json
import requests
from typing import Optional, Dict, Any
from config import CONFIG

from services.redis_client import redis_client


# ---------------- ПРОФИЛИ ----------------

def _load_profile(profile_key: str) -> Optional[Dict[str, Any]]:
    profile = CONFIG["profiles"].get(profile_key)

    if not profile:
        print(f"❌ Профиль {profile_key} не найден в CONFIG")
        return None

    if not isinstance(profile, dict):
        print(f"❌ Профиль {profile_key} имеет неверный формат (ожидался dict)")
        return None

    return profile


# ---------------- REDIS ----------------

def _get_utoken_from_redis(uid: str) -> Optional[str]:
    raw = redis_client.hget("connected_users", uid)
    if not raw:
        return None

    try:
        user_data = json.loads(raw)
        return user_data.get("utoken")
    except Exception:
        return None


# ---------------- CLOUD ВИБРАЦИЯ ----------------

def send_vibration_cloud(profile_key: str, strength: int, duration: int) -> Optional[dict]:
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
