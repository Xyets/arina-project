import json
import aiohttp
from typing import Optional, Dict, Any

from services.redis_client import redis_client
from services.database import get_profile_by_key, get_model_by_id


# ---------------- UTOKEN ----------------

def _get_utoken(profile_key: str) -> Optional[str]:
    """
    Получает utoken из Redis по profile_key.
    """
    raw = redis_client.hget("connected_users", profile_key)
    if not raw:
        return None

    try:
        data = json.loads(raw)
        return data.get("utoken")
    except Exception:
        return None


# ---------------- CLOUD API ----------------

async def start_vibration_cloud_async(profile_key: str, strength: int, duration: int):
    """
    Запускает вибрацию через Lovense Cloud API.
    """
    profile = get_profile_by_key(profile_key)
    if not profile:
        print(f"❌ Профиль {profile_key} не найден")
        return

    model = get_model_by_id(profile["model_id"])
    if not model:
        print(f"❌ Модель для профиля {profile_key} не найдена")
        return

    uid = model["uid"]
    developer_token = model["lovense_token"]
    utoken = _get_utoken(profile_key)

    if not utoken:
        print(f"❌ [{profile_key}] utoken отсутствует — игрушка не подключена")
        return

    url = "https://api.lovense.com/api/lan/v2/command"

    payload = {
        "token": developer_token,
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": f"Vibrate:{strength}",
        "timeSec": duration,
    }

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload, timeout=2)
    except Exception as e:
        print("Ошибка Cloud API:", e)


async def stop_vibration_cloud_async(profile_key: str):
    """
    Останавливает вибрацию мгновенно.
    """
    profile = get_profile_by_key(profile_key)
    if not profile:
        print(f"❌ Профиль {profile_key} не найден")
        return

    model = get_model_by_id(profile["model_id"])
    if not model:
        print(f"❌ Модель для профиля {profile_key} не найдена")
        return

    uid = model["uid"]
    developer_token = model["lovense_token"]
    utoken = _get_utoken(profile_key)

    if not utoken:
        print(f"❌ [{profile_key}] utoken отсутствует — игрушка не подключена")
        return

    url = "https://api.lovense.com/api/lan/v2/command"

    payload = {
        "token": developer_token,
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": "Vibrate:0",
        "timeSec": 0,
    }

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload, timeout=2)
    except Exception as e:
        print("Ошибка Cloud API:", e)


# ---------------- СОВМЕСТИМОСТЬ С WS_APP ----------------

async def send_vibration_cloud_async(profile_key: str, strength: int, duration: int):
    """
    Совместимость с ws_app:
    - если strength > 0 → старт вибрации
    - если strength == 0 → стоп вибрации
    duration игнорируется — worker сам управляет временем.
    """
    if strength > 0:
        await start_vibration_cloud_async(profile_key, strength, duration)
    else:
        await stop_vibration_cloud_async(profile_key)
