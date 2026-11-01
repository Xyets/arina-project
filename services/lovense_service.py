import json
import aiohttp
from services.logs_service import add_error_log
from services.redis_client import redis_client
from services.database import get_profile_by_key, get_model_by_id



def _record_lovense_issue(level: str, profile_key: str, operation: str, detail: str):
    """Записывает диагностику Lovense без токенов и пользовательских данных."""
    try:
        add_error_log(level, f"component=lovense operation={operation} profile={profile_key!r} {detail}")
    except Exception:
        # Диагностика не должна ломать управление вибрацией.
        pass


def _is_successful_response(http_status, result):
    return (
        int(http_status) == 200
        and str(result.get("code")) == "200"
        and result.get("result") is not False
    )

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
        return json.loads(raw).get("utoken")
    except:
        return None


# ---------------- CLOUD API ----------------

async def start_vibration_cloud_async(profile_key: str, strength: int):
    """
    LAN API НЕ УМЕЕТ duration → timeSec всегда 0.
    Worker сам управляет временем вибрации.
    """
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
        _record_lovense_issue("WARNING", profile_key, "start_vibration", "reason=utoken_missing")
        return

    url = "https://api.lovense-api.com/api/lan/v2/command"

    payload = {
        "token": token,
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": f"Vibrate:{strength}",
        "timeSec": 0,   # Worker управляет временем остановки.
        "apiVer": 1,
    }

    try:
        async with session.post(url, json=payload, timeout=5) as response:
            try:
                result = await response.json(content_type=None)
            except Exception:
                result = {}
            print(
                f"Lovense command: profile={profile_key}, "
                f"http_status={response.status}, "
                f"code={result.get('code')}, "
                f"message={result.get('message', '')}"
            )
            if not _is_successful_response(response.status, result):
                _record_lovense_issue(
                    "ERROR", profile_key, "start_vibration",
                    f"http_status={response.status} code={result.get('code')!r} "
                    f"message={str(result.get('message', ''))[:200]!r}"
                )
    except Exception as e:
        print(f"Ошибка Lovense API: {type(e).__name__}")
        _record_lovense_issue(
            "ERROR", profile_key, "start_vibration",
            f"exception={type(e).__name__}: {str(e)[:200]!r}"
        )


async def stop_vibration_cloud_async(profile_key: str):
    """
    STOP — единственный способ остановить вибрацию в LAN API.
    """
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
        _record_lovense_issue("WARNING", profile_key, "stop_vibration", "reason=utoken_missing")
        return

    url = "https://api.lovense-api.com/api/lan/v2/command"

    payload = {
        "token": token,
        "uid": uid,
        "utoken": utoken,
        "command": "Function",
        "action": "Vibrate:0",
        "timeSec": 0,
        "apiVer": 1,
    }

    try:
        async with session.post(url, json=payload, timeout=5) as response:
            try:
                result = await response.json(content_type=None)
            except Exception:
                result = {}
            print(
                f"Lovense command: profile={profile_key}, "
                f"http_status={response.status}, "
                f"code={result.get('code')}, "
                f"message={result.get('message', '')}"
            )
            if not _is_successful_response(response.status, result):
                _record_lovense_issue(
                    "ERROR", profile_key, "stop_vibration",
                    f"http_status={response.status} code={result.get('code')!r} "
                    f"message={str(result.get('message', ''))[:200]!r}"
                )
    except Exception as e:
        print(f"Ошибка Lovense API: {type(e).__name__}")
        _record_lovense_issue(
            "ERROR", profile_key, "stop_vibration",
            f"exception={type(e).__name__}: {str(e)[:200]!r}"
        )


async def send_vibration_cloud_async(profile_key: str, strength: int, duration: int):
    """
    Совместимость с ws_app:
    - strength > 0 → старт вибрации
    - strength == 0 → стоп вибрации
    duration игнорируется — worker сам управляет временем.
    """
    if strength > 0:
        await start_vibration_cloud_async(profile_key, strength)
    else:
        await stop_vibration_cloud_async(profile_key)
