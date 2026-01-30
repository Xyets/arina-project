from flask import Blueprint, request
import json

from services.lovense_service import redis_client

lovense_bp = Blueprint("lovense", __name__)
from flask import render_template
from services.lovense_service import get_qr_code_for_profile
from config import CONFIG

@lovense_bp.route("/qrcode/<profile_key>")
def qrcode_page(profile_key):
    profile = CONFIG["profiles"].get(profile_key)
    if not profile:
        return "Профиль не найден", 404

    qr_url = get_qr_code_for_profile(profile)
    if not qr_url:
        return "Не удалось получить QR‑код", 500

    return render_template(
        "qrcode.html",
        user=profile["uname"],
        qr_url=qr_url
    )


@lovense_bp.route("/lovense/callback", methods=["POST"])
def lovense_callback():
    """
    Callback от Lovense Cloud.
    Сохраняет utoken и список игрушек в Redis.
    """
    data = request.json or request.form
    uid = data.get("uid")

    if not uid:
        return "❌ Нет uid", 400

    payload = {
        "utoken": data.get("utoken"),
        "toys": data.get("toys", {}),
    }

    redis_client.hset("connected_users", uid, json.dumps(payload, ensure_ascii=False))
    print("🔐 CONNECTED_USERS обновлён:", uid)

    return "✅ Callback принят", 200
