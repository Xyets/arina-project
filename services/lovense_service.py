import json
import aiohttp
from services.redis_client import redis_client
from services.database import get_profile_by_key, get_model_by_id

session: aiohttp.ClientSession = None

async def init_lovense_session():
    global session
    if session is None:
        session = aiohttp.ClientSession()

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
        return json.loads(raw).get("utoken")
    except:
        return None


async def start_vibration_cloud_async(profile_key: str, strength: int):
    await init_lovense_session()

    profile = get_profile_by_key(profile_key)
    if not profile:
        return

    model = get_model_by_id(profile["model_id"])
    if not model:
        return

    uid = model["uid"]
    token = model["lovense_token"]
    utoken = _get_utoken(profile_key)

    if not utoken:
        print(f"❌ [{profile_key}] utoken отсутствует")
        return

    url = "https://api.lovense.com/api/lan/v2/command"

    payload = {
        "token": token,
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": f"Vibrate:{strength}",
        "timeSec": 0,   # LAN API НЕ УМЕЕТ duration
    }

    try:
        await session.post(url, json=payload, timeout=1)
    except Exception as e:
        print("Ошибка Cloud API:", e)


async def stop_vibration_cloud_async(profile_key: str):
    await init_lovense_session()

    profile = get_profile_by_key(profile_key)
    if not profile:
        return

    model = get_model_by_id(profile["model_id"])
    if not model:
        return

    uid = model["uid"]
    token = model["lovense_token"]
    utoken = _get_utoken(profile_key)

    if not utoken:
        print(f"❌ [{profile_key}] utoken отсутствует")
        return

    url = "https://api.lovense.com/api/lan/v2/command"

    payload = {
        "token": token,
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
    if strength > 0:
        await start_vibration_cloud_async(profile_key, strength)
    else:
        await stop_vibration_cloud_async(profile_key)
