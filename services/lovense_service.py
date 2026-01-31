import json
import requests
import redis
from typing import Optional, Dict, Any
from config import CONFIG


# ---------------- REDIS ----------------

redis_client = redis.StrictRedis(
    host=CONFIG.get("redis_host", "localhost"),
    port=CONFIG.get("redis_port", 6379),
    db=0
)


# ---------------- УТИЛИТЫ ----------------

def generate_utoken(uid: str) -> str:
    """
    В новой версии utoken НЕ генерируется вручную.
    Он приходит из callback Lovense Cloud.
    """
    return ""


# ---------------- QR-КОД ----------------

def get_qr_code_for_profile(profile: Dict[str, Any]) -> Optional[str]:
    """
    Возвращает QR-код для подключения игрушки Lovense.
    """
    url = "https://api.lovense.com/api/lan/getQrCode"

    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": profile["uid"],
        "uname": profile["uname"],
        "utoken": "",  # utoken приходит из callback
        "callbackUrl": CONFIG.get("lovense_callback_url"),
        "v": 2,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
    except Exception as e:
        print(f"❌ Ошибка получения QR-кода: {e}")
        return None

    # Успешный ответ
    if data.get("code") == 0:
        qr = data.get("data", {}).get("qr")
        if qr:
            return qr

    # Иногда API возвращает QR в message
    msg = data.get("message")
    if isinstance(msg, str) and msg.startswith("http"):
        return msg

    return None


# ---------------- CLOUD ВИБРАЦИЯ ----------------

def _get_utoken_from_redis(uid: str) -> Optional[str]:
    """
    Возвращает utoken из Redis, если игрушка подключена.
    """
    raw = redis_client.hget("connected_users", uid)
    if not raw:
        return None

    try:
        user_data = json.loads(raw)
        return user_data.get("utoken")
    except Exception:
        return None


def send_vibration_cloud(profile: Dict[str, Any], strength: int, duration: int) -> Optional[dict]:
    """
    Отправляет вибрацию в Lovense Cloud.
    """
    uid = profile["uid"]
    utoken = _get_utoken_from_redis(uid)

    if not utoken:
        print(f"❌ Игрушка {uid} не подключена или utoken отсутствует")
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
        print(f"❌ Ошибка Cloud-вибрации: {e}")
        return None


def stop_vibration_cloud(profile: Dict[str, Any]) -> Optional[dict]:
    """
    Останавливает вибрацию в Lovense Cloud.
    """
    uid = profile["uid"]
    utoken = _get_utoken_from_redis(uid)

    if not utoken:
        print(f"❌ Игрушка {uid} не подключена или utoken отсутствует")
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
        print(f"❌ Ошибка остановки вибрации: {e}")
        return None
