from flask import Blueprint, request
import json

from services.lovense_service import redis_client

lovense_bp = Blueprint("lovense", __name__)


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
