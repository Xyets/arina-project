
from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import json
import requests
from flask import send_file
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
        return "❌ Не удалось получить QR-код", 500

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
        return "❌ Не удалось получить QR-код", 500

    return render_template(
        "qrcode.html",
        user=model["display_name"],
        qr_url=qr_url,
    )


# -------------------- ФУНКЦИЯ ПОЛУЧЕНИЯ QR-КОДА --------------------

def get_qr_code(profile_key):
    profile = get_profile_by_key(profile_key)
    if not profile:
        return None

    model = get_model_by_id(profile["model_id"])
    if not model:
        return None

    if not model["uid"] or not model["lovense_token"]:
        print(f"❌ [{profile_key}] В SQL отсутствует UID или Lovense token")
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
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        print("Ответ от Lovense API:", data)
    except Exception as e:
        print("Ошибка запроса QR:", e)
        return None

    if (
        data.get("code") == 0
        and isinstance(data.get("data"), dict)
        and data["data"].get("qr")
    ):
        return data["data"]["qr"]

    message = data.get("message")
    if isinstance(message, str) and message.startswith("http"):
        return message

    print("❌ Lovense не вернул QR-код")
    return None


# -------------------- CALLBACK ОТ LOVENSE CLOUD --------------------

@lovense_bp.route("/callback", methods=["POST"])
@lovense_bp.route("/lovense/callback", methods=["POST"])
def lovense_callback():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        data = request.form.to_dict()

    uid = str(data.get("uid") or "").strip()
    supplied_utoken = str(data.get("utoken") or "").strip()

    # -------------------- ТЕСТОВЫЕ ПОДКЛЮЧЕНИЯ --------------------

    test_profiles = {
        "flowtip_test_arina_a": "a",
        "flowtip_test_arina_b": "b",
    }

    if uid in test_profiles:
        from app.lovense_test_app import _load_state, _save_state
        import hmac

        slot = test_profiles[uid]
        state = _load_state()
        expected_utoken = str(state[slot].get("utoken") or "")

        if (
            not expected_utoken
            or not supplied_utoken
            or not hmac.compare_digest(expected_utoken, supplied_utoken)
        ):
            return "Invalid test user token", 403

        if isinstance(data.get("toys"), dict):
            state[slot]["toys"] = data["toys"]

        toys = state[slot].get("toys") or {}
        state[slot]["connected"] = any(
            isinstance(toy, dict)
            and str(toy.get("status", "")) == "1"
            for toy in toys.values()
        )

        _save_state(state)
        return "OK", 200

    # -------------------- РАБОЧИЕ МОДЕЛИ --------------------

    if not uid:
        return "Missing uid", 400

    model = get_model_by_uid(uid)
    if not model:
        return "Model not found", 404

    # Подключение каждой модели хранится по её собственному UID.
    # Читаем предыдущее состояние, чтобы не затереть utoken,
    # если очередное уведомление пришло без этого поля.
    raw_previous = redis_client.hget("connected_users", uid)
    previous = {}

    if raw_previous:
        try:
            if isinstance(raw_previous, bytes):
                raw_previous = raw_previous.decode("utf-8")
            parsed = json.loads(raw_previous)
            if isinstance(parsed, dict):
                previous = parsed
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            print(
                f"⚠️ [{model['username']}] "
                "Не удалось прочитать прежнее состояние Lovense"
            )

    # Обновляем utoken только если новое уведомление содержит
    # непустое значение. Пустое поле не должно затирать старый токен.
    utoken = supplied_utoken or str(previous.get("utoken") or "")

    # Если toys присутствует и имеет правильный тип, обновляем его.
    # Если поле отсутствует или некорректно, сохраняем предыдущие данные.
    incoming_toys = data.get("toys")
    if isinstance(incoming_toys, dict):
        toys = incoming_toys
    else:
        toys = previous.get("toys", {})
        if not isinstance(toys, dict):
            toys = {}

    payload = {
        "utoken": utoken,
        "toys": toys,
    }

    redis_client.hset(
        "connected_users",
        uid,
        json.dumps(payload, ensure_ascii=False),
    )

    connected = any(
        isinstance(toy, dict)
        and str(toy.get("status", "")) == "1"
        for toy in toys.values()
    )

    print(
        f"Lovense callback: model={model['username']}, "
        f"utoken_present={bool(utoken)}, "
        f"toys_count={len(toys)}, connected={connected}"
    )

    return "OK", 200


# -------------------- ИЗОБРАЖЕНИЕ QR-КОДА --------------------

@lovense_bp.route("/qrcode_image/<profile_key>")
@login_required
def qrcode_image(profile_key):
    qr_url = get_qr_code(profile_key)
    if not qr_url:
        return "QR not found", 404

    try:
        response = requests.get(qr_url, timeout=10)
        response.raise_for_status()

        img_bytes = BytesIO(response.content)
        return send_file(img_bytes, mimetype="image/png")
    except Exception as e:
        print("Ошибка загрузки QR:", e)
        return "QR load error", 500


# -------------------- API ДЛЯ QR-КОДА --------------------

@lovense_bp.route("/qr_generate")
@login_required
def qr_generate():
    user = session["username"]
    mode = session.get("mode", "public")
    profile_key = f"{user}_{mode}"

    qr_url = get_qr_code(profile_key)
    if not qr_url:
        return {"status": "error", "qr": None}, 500

    return {"status": "ok", "qr": qr_url}
