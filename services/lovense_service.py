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


# ---------------- CLOUD API ----------------

async def start_vibration_cloud_async(profile_key: str, strength: int, duration: int):
    profile = _load_profile(profile_key)
    if not profile:
        return

    uid = profile["uid"]
    utoken = _get_utoken_from_redis(uid)
    if not utoken:
        print(f"❌ [{profile_key}] utoken отсутствует — игрушка не подключена")
        return

    url = "https://api.lovense.com/api/lan/v2/command"

    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": f"Vibrate:{strength}",
        "timeSec": duration,   # 🔥 снова даём duration в Lovense
    }

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload, timeout=1)
    except Exception:
        pass


async def stop_vibration_cloud_async(profile_key: str):
    """
    Останавливает вибрацию мгновенно.
    """
    profile = _load_profile(profile_key)
    if not profile:
        return

    uid = profile["uid"]
    utoken = _get_utoken_from_redis(uid)
    if not utoken:
        print(f"❌ [{profile_key}] utoken отсутствует — игрушка не подключена")
        return

    url = "https://api.lovense.com/api/lan/v2/command"

    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": "Vibrate:0",
        "timeSec": 0,
    }

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload, timeout=1)
    except Exception:
        pass
# ---------------- СОВМЕСТИМОСТЬ С WS_APP ----------------

async def send_vibration_cloud_async(profile_key: str, strength: int, duration: int):
    """
    Эта функция нужна для совместимости с ws_app.py.
    Она вызывает start/stop в зависимости от силы.
    duration игнорируется — длительность контролирует vibration_worker.
    """
    if strength > 0:
        await start_vibration_cloud_async(profile_key, strength)
    else:
        await stop_vibration_cloud_async(profile_key)