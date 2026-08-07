import json
import aiohttp
from typing import Optional, Dict, Any

from services.redis_client import redis_client
from services.database import get_profile_by_key, get_model_by_id

# ---------------- ГЛОБАЛЬНАЯ СЕССИЯ ----------------

session: aiohttp.ClientSession = None

async def init_lovense_session():
    global session
    if session is None:
        session = aiohttp.ClientSession()


# ---------------- UTOKEN ----------------

def _get_utoken(profile_key: str):
    profile = get_profile_by_key(profile_key)
    if not profile:
        return None

    model = get_model_by_id(profile["model_id"])
    if not model:
        return None

    uid = model["uid"]

    raw = redis_client.hget("connected_users", uid)
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
    🔥 ВАЖНО:
    - duration снова отправляется в Lovense
    - игрушка сама остановится ровно через duration секунд
    - worker НЕ должен отправлять STOP при NATURAL END
    """
    await init_lovense_session()

    profile = get_profile_by_key(profile_key)
    if not profile:
        return

    model = get_model_by_id(profile["model_id"])
    if not model:
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
        "timeSec": duration,   # 🔥 duration снова используется
    }

    try:
        await session.post(url, json=payload, timeout=1)
    except Exception as e:
        print("Ошибка Cloud API:", e)


async def stop_vibration_cloud_async(profile_key: str):
    """
    🔥 STOP — мгновенный, ручной.
    Используется только при нажатии кнопки STOP или прерывании вибрации worker'ом.
    """
    await init_lovense_session()

    profile = get_profile_by_key(profile_key)
    if not profile:
        return

    model = get_model_by_id(profile["model_id"])
    if not model:
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
        await session.post(url, json=payload, timeout=1)
    except Exception as e:
        print("Ошибка Cloud API:", e)


async def send_vibration_cloud_async(profile_key: str, strength: int, duration: int):
    """
    🔥 Совместимость с ws_app:
    - strength > 0 → старт вибрации с duration
    - strength == 0 → стоп вибрации
    """
    if strength > 0:
        await start_vibration_cloud_async(profile_key, strength, duration)
    else:
        await stop_vibration_cloud_async(profile_key)
