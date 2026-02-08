from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import json
import requests

from config import CONFIG
from services.redis_client import redis_client   # ← ЕДИНСТВЕННЫЙ ПРАВИЛЬНЫЙ ИМПОРТ

lovense_bp = Blueprint("lovense", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- QR-КОД (АВТОМАТИЧЕСКИЙ) --------------------

@lovense_bp.route("/qrcode")
@login_required
def qrcode_default():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    qr_url = get_qr_code(profile_key)
    if not qr_url:
        return "❌ Не удалось получить QR‑код", 500

    return render_template("qrcode.html", user=user, qr_url=qr_url)


# -------------------- QR-КОД (ЯВНЫЙ ПРОФИЛЬ) --------------------

@lovense_bp.route("/qrcode/<profile_key>")
@login_required
def qrcode_page(profile_key):
    profile = CONFIG["profiles"].get(profile_key)
    if not profile:
        return "Профиль не найден", 404

    qr_url = get_qr_code(profile_key)
    if not qr_url:
        return "❌ Не удалось получить QR‑код", 500

    return render_template("qrcode.html", user=profile["uname"], qr_url=qr_url)


# -------------------- ФУНКЦИЯ ПОЛУЧЕНИЯ QR-КОДА --------------------

def get_qr_code(profile_key):
    profile = CONFIG["profiles"][profile_key]
    url = "https://api.lovense.com/api/lan/getQrCode"

    payload = {
        "token": profile["DEVELOPER_TOKEN"],
        "uid": profile["uid"],
        "uname": profile["uname"],
        "utoken": "",
        "callbackUrl": "https://arinairina.duckdns.org/lovense/callback",
        "v": 2,
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        print("Ответ от Lovense API:", data)
    except Exception as e:
        print("Ошибка запроса QR:", e)
        return None

    if data.get("code") == 0 and "data" in data and "qr" in data["data"]:
        return data["data"]["qr"]

    msg = data.get("message")
    if isinstance(msg, str) and msg.startswith("http"):
        return msg

    return None


# -------------------- CALLBACK ОТ LOVENSE CLOUD --------------------

@lovense_bp.route("/callback", methods=["POST"])
def lovense_callback():
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
