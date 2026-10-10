
import json
import hmac
import secrets
import os
from pathlib import Path
from functools import wraps

import requests
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
)

from services.database import get_model_by_username


lovense_test_bp = Blueprint(
    "lovense_test",
    __name__,
    url_prefix="/lovense-test",
)

ROOT = Path(__file__).resolve().parent.parent
SECRET_FILE = ROOT / "config" / "lovense_test_secret.txt"
STATE_FILE = ROOT / "data" / "lovense_test_state.json"

QR_API = "https://api.lovense-api.com/api/lan/getQrCode"
COMMAND_API = "https://api.lovense-api.com/api/lan/v2/command"
CALLBACK_BASE = "https://arinairina.duckdns.org/lovense-test/callback"

# Только тестовые UID. Не совпадают с UID рабочих профилей.
TEST_PROFILES = {
    "a": {
        "uid": "flowtip_test_arina_a",
        "uname": "FlowTip Test A",
        "label": "Устройство A",
    },
    "b": {
        "uid": "flowtip_test_arina_b",
        "uname": "FlowTip Test B",
        "label": "Устройство B",
    },
}


def _read_secret():
    try:
        value = SECRET_FILE.read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None


def _load_state():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}

    changed = False

    for slot, profile in TEST_PROFILES.items():
        if slot not in state or not isinstance(state[slot], dict):
            state[slot] = {}
            changed = True

        item = state[slot]

        if not item.get("utoken"):
            item["utoken"] = secrets.token_urlsafe(32)
            changed = True

        if "connected" not in item:
            item["connected"] = False
            changed = True

        if "toys" not in item or not isinstance(item["toys"], dict):
            item["toys"] = {}
            changed = True

        # UID берём только из констант, а не из запроса пользователя.
        item["uid"] = profile["uid"]

    if changed or not STATE_FILE.exists():
        _save_state(state)

    return state


def _save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = STATE_FILE.with_suffix(".tmp")
    temp_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.chmod(temp_file, 0o600)
    temp_file.replace(STATE_FILE)
    os.chmod(STATE_FILE, 0o600)


def _get_slot(slot):
    if slot not in TEST_PROFILES:
        return None
    return slot, TEST_PROFILES[slot]


def _public_status():
    state = _load_state()
    result = {}

    for slot, profile in TEST_PROFILES.items():
        item = state[slot]
        toys = item.get("toys", {})

        toy_list = []
        if isinstance(toys, dict):
            for toy_id, toy in toys.items():
                if not isinstance(toy, dict):
                    continue
                toy_list.append({
                    "name": str(
                        toy.get("nickName")
                        or toy.get("name")
                        or "Lovense toy"
                    )[:80],
                    "status": str(toy.get("status", "")),
                })

        result[slot] = {
            "label": profile["label"],
            "uid": profile["uid"],
            "connected": bool(item.get("connected")),
            "toys": toy_list,
        }

    return result


def test_login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        username = session.get("username")

        if not username:
            return redirect(url_for("panel.login"))

        # Не разрешаем другим аккаунтам использовать тестовый токен Arina.
        if username != "Arina":
            return "Доступ запрещён", 403

        return function(*args, **kwargs)

    return wrapper


def _get_arina_token():
    # Используем токен из действующей БД, не из старого config.json.
    model = get_model_by_username("Arina")
    if not model:
        raise RuntimeError("Аккаунт Arina не найден в базе данных.")

    token = model["lovense_token"]
    if not token:
        raise RuntimeError("У Arina не настроен Lovense Developer Token.")

    return token


@lovense_test_bp.route("/", methods=["GET"])
@test_login_required
def index():
    # Инициализируем временные utoken до создания QR-кодов.
    _load_state()
    return render_template("lovense_test.html")


@lovense_test_bp.route("/api/status", methods=["GET"])
@test_login_required
def api_status():
    return jsonify({"status": "ok", "devices": _public_status()})


@lovense_test_bp.route("/api/qr/<slot>", methods=["POST"])
@test_login_required
def api_qr(slot):
    selected = _get_slot(slot)
    if not selected:
        return jsonify({"status": "error", "message": "Неизвестный слот."}), 404

    secret = _read_secret()
    if not secret:
        return jsonify({
            "status": "error",
            "message": "Не найден секрет callback. Проверьте config/lovense_test_secret.txt.",
        }), 500

    try:
        token = _get_arina_token()
        state = _load_state()
        profile = selected[1]

        callback_url = f"{CALLBACK_BASE}?secret={secret}"

        payload = {
            "token": token,
            "uid": profile["uid"],
            "uname": profile["uname"],
            "utoken": state[slot]["utoken"],
            "callbackUrl": callback_url,
            "v": 2,
        }

        response = requests.post(QR_API, json=payload, timeout=15)
        data = response.json()

        if data.get("code") == 0 and data.get("data", {}).get("qr"):
            return jsonify({
                "status": "ok",
                "qr": data["data"]["qr"],
            })

        # Не возвращаем payload или Developer Token в браузер.
        message = str(data.get("message") or "Lovense не выдал QR-код.")
        return jsonify({
            "status": "error",
            "message": message[:250],
        }), 502

    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Не удалось связаться с Lovense API.",
        }), 502
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Ошибка подготовки QR-кода. Проверьте журнал приложения.",
        }), 500


@lovense_test_bp.route("/api/command/<slot>", methods=["POST"])
@test_login_required
def api_command(slot):
    selected = _get_slot(slot)
    if not selected:
        return jsonify({"status": "error", "message": "Неизвестный слот."}), 404

    body = request.get_json(silent=True) or {}
    action_type = body.get("action")

    if action_type not in ("vibrate", "stop"):
        return jsonify({
            "status": "error",
            "message": "Разрешены только команды vibrate и stop.",
        }), 400

    try:
        state = _load_state()
        profile = selected[1]
        item = state[slot]

        # Не отправляем команды, пока callback не подтвердил подключение.
        if not item.get("connected") or not item.get("toys"):
            return jsonify({
                "status": "error",
                "message": "Устройство ещё не подтвердило подключение. Сначала отсканируйте QR-код.",
            }), 409

        payload = {
            "token": _get_arina_token(),
            "uid": profile["uid"],
            "command": "Function",
            "action": "Vibrate:3" if action_type == "vibrate" else "Stop",
            "timeSec": 2,
            "apiVer": 1,
        }

        response = requests.post(COMMAND_API, json=payload, timeout=15)
        data = response.json()

        if data.get("code") == 200:
            return jsonify({
                "status": "ok",
                "message": (
                    "Команда отправлена: вибрация 3/20 на 2 секунды."
                    if action_type == "vibrate"
                    else "Команда остановки отправлена."
                ),
            })

        message = str(data.get("message") or data.get("type") or "Lovense отклонил команду.")
        return jsonify({
            "status": "error",
            "message": message[:250],
        }), 502

    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Не удалось связаться с Lovense API.",
        }), 502
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Ошибка отправки команды. Проверьте журнал приложения.",
        }), 500


@lovense_test_bp.route("/callback", methods=["POST"])
def callback():
    # Callback вызывается Lovense без пользовательской Flask-сессии.
    expected_secret = _read_secret()
    supplied_secret = request.args.get("secret", "")

    if (
        not expected_secret
        or not supplied_secret
        or not hmac.compare_digest(expected_secret, supplied_secret)
    ):
        return "Forbidden", 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = request.form.to_dict()

    uid = str(data.get("uid") or "")
    slot = next(
        (key for key, profile in TEST_PROFILES.items()
         if profile["uid"] == uid),
        None,
    )

    if not slot:
        return "Unknown test UID", 404

    state = _load_state()
    item = state[slot]

    # Дополнительно сверяем utoken, чтобы не принимать чужой callback.
    supplied_utoken = str(data.get("utoken") or "")
    if not supplied_utoken or not hmac.compare_digest(
        str(item["utoken"]), supplied_utoken
    ):
        return "Invalid user token", 403

    toys = data.get("toys", {})
    if not isinstance(toys, dict):
        toys = {}

    item["toys"] = toys
    item["connected"] = any(
        isinstance(toy, dict) and str(toy.get("status", "")) == "1"
        for toy in toys.values()
    )

    _save_state(state)
    return "OK", 200
