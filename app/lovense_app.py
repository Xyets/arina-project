from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import json
import requests
from flask import send_file
import requests
from io import BytesIO

from services.database import (
    get_profile_by_key,
    get_model_by_id,
    get_model_by_uid,
)
from services.redis_client import redis_client

lovense_bp = Blueprint("lovense", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- QR-КОД (АВТОМАТИЧЕСКИЙ) --------------------

@lovense_bp.route("/qrcode")
@login_required
def qrcode_default():
    user = session["username"]
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
    profile = get_profile_by_key(profile_key)
    if not profile:
        return "Профиль не найден", 404

    model = get_model_by_id(profile["model_id"])
    if not model:
        return "Модель не найдена", 404

    qr_url = get_qr_code(profile_key)
    if not qr_url:
        return "❌ Не удалось получить QR‑код", 500

    return render_template("qrcode.html", user=model["display_name"], qr_url=qr_url)


# -------------------- ФУНКЦИЯ ПОЛУЧЕНИЯ QR-КОДА --------------------

def get_qr_code(profile_key):
    profile = get_profile_by_key(profile_key)
    if not profile:
        return None

    model = get_model_by_id(profile["model_id"])
    if not model:
        return None

    url = "https://api.lovense.com/api/lan/getQrCode"

    payload = {
        "token": model["lovense_token"],
        "uid": model["uid"],
        "uname": model["display_name"],
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

    model = get_model_by_uid(uid)
    if not model:
        return "❌ Модель не найдена", 404

    # всегда считаем, что игрушка привязана к public‑профилю модели
    profile_key = f"{model['username']}_public"

    payload = {
        "utoken": data.get("utoken"),
        "toys": data.get("toys", {}),
    }

    redis_client.hset(
        "connected_users",
        profile_key,
        json.dumps(payload, ensure_ascii=False)
    )

    print("🔐 CONNECTED_USERS обновлён:", profile_key)
    return "✅ Callback принят", 200


@lovense_bp.route("/qrcode_image/<profile_key>")
@login_required
def qrcode_image(profile_key):
    qr_url = get_qr_code(profile_key)
    if not qr_url:
        return "QR not found", 404

    # скачиваем изображение QR-кода
    try:
        r = requests.get(qr_url, timeout=10)
        img_bytes = BytesIO(r.content)
        return send_file(img_bytes, mimetype="image/png")
    except Exception as e:
        print("Ошибка загрузки QR:", e)
        return "QR load error", 500
