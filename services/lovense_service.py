import json
import aiohttp
from typing import Optional, Dict, Any

from config import CONFIG
from services.redis_client import redis_client


# ---------------- ПРОФИЛИ ----------------

def _load_profile(profile_key: str) -> Optional[Dict[str, Any]]:
    profile = CONFIG["profiles"].get(profile_key)
    if not profile:
        print(f"❌ Профиль {profile_key} не найден в CONFIG")
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


# ---------------- ASYNC CLOUD ВИБРАЦИЯ ----------------

async def send_vibration_cloud_async(profile_key: str, strength: int, duration: int):
    profile = _load_profile(profile_key)
    if not profile:
        return None

    uid = profile.get("uid")
    utoken = _get_utoken_from_redis(uid)

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
        async with aiohttp.ClientSession() as session:
            # 🔥 НЕ ЖДЁМ ОТВЕТ — просто отправляем и идём дальше
            await session.post(url, json=payload, timeout=1)
    except Exception:
        pass

async def stop_vibration_cloud_async(profile_key: str) -> Optional[dict]:
    return await send_vibration_cloud_async(profile_key, 0, 0)
