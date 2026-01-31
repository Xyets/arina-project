from flask import Blueprint, request, render_template
import json
import requests

from config import CONFIG
from services.lovense_service import redis_client, generate_utoken

lovense_bp = Blueprint("lovense", __name__)


# -------------------- QR‑КОД ДЛЯ ПОДКЛЮЧЕНИЯ --------------------

@lovense_bp.route("/qrcode/<profile_key>")
def qrcode_page(profile_key):
    """
    Страница с QR‑кодом для подключения Lovense (LAN API, как раньше).
    """
    profile = CONFIG["profiles"].get(profile_key)
    if not profile:
        return "Профиль не найден", 404

    qr_url = get_qr_code(profile_key)
    if not qr_url:
        return "Не удалось получить QR‑код", 500

    return render_template(
        "qrcode.html",
        user=profile["uname"],
        qr_url=qr_url
    )


def get_qr_code(profile_key):
    """
    СТАРЫЙ РЕЖИМ — LAN API.
    Работает ВСЕГДА, даже если игрушка не подключена.
    """
    profile = CONFIG["profiles"][profile_key]
    url = "https://api.lovense.com/api/lan/getQrCode"

    uid = profile["uid"]
    utoken = generate_utoken(uid)  # как раньше

    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": uid,
        "uname": profile["uname"],
        "utoken": utoken,
        "callbackUrl": "https://arinairina.duckdns.org/lovense/callback?token=arina_secret_123",
        "v": 2,
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        print("Ответ от Lovense API:", data)
    except Exception as e:
        print("Ошибка запроса QR:", e)
        return None

    # Успешный ответ
    if data.get("code") == 0 and "data" in data and "qr" in data["data"]:
        return data["data"]["qr"]

    # Иногда QR приходит в message
    msg = data.get("message")
    if isinstance(msg, str) and msg.startswith("http"):
        return msg

    return None


# -------------------- CALLBACK ОТ LOVENSE CLOUD --------------------

@lovense_bp.route("/callback", methods=["POST"])
def lovense_callback():
    """
    Callback от Lovense Cloud (как раньше).
    """
    data = request.json or request.form or {}
    print("📩 Callback от Lovense:", data)

    uid = data.get("uid")
    if not uid:
        return "❌ Нет uid", 400

    payload = {
        "utoken": data.get("utoken"),
        "toys": data.get("toys", {}),
    }

    redis_client.hset(
        "connected_users",
        uid,
        json.dumps(payload, ensure_ascii=False)
    )

    print("🔐 CONNECTED_USERS (Redis) обновлён:", uid)
    return "✅ Callback принят", 200
