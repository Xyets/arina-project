from flask import Blueprint, render_template, session, redirect, url_for 
from functools import wraps 
from config import CONFIG 
from services.lovense_service import redis_client, generate_utoken
import requests 
import json
from flask import Blueprint, request, render_template, session, redirect, url_for

lovense_bp = Blueprint("lovense", __name__)

def login_required(f): 
    @wraps(f) 
    def wrapper(*args, **kwargs): 
        if "user" not in session: 
            return redirect(url_for("panel.login")) 
        return f(*args, **kwargs) 
    return wrapper
# -------------------- QR‑КОД ДЛЯ ПОДКЛЮЧЕНИЯ --------------------

@lovense_bp.route("/qrcode") 
@login_required 
def qrcode_default(): 
    """ Старый режим: /qrcode без параметров. Автоматически определяет профиль текущего пользователя. """ 
    user = session["user"] 
    mode = session.get("mode", "private") 
    profile_key = f"{user}_{mode}" 
    qr_url = get_qr_code(profile_key) 
    if not qr_url: 
        return "❌ Не удалось получить QR‑код", 500 
    return render_template("qrcode.html", user=user, qr_url=qr_url)


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
    Callback от Lovense Cloud.
    Получает utoken и список игрушек, сохраняет в Redis.
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

    print("🔐 CONNECTED_USERS обновлён:", uid)
    return "✅ Callback принят", 200
