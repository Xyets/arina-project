from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from functools import wraps

from services.vip_service import load_vip_file, save_vip_file
from config import CONFIG

vip_bp = Blueprint("vip", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- VIP PAGE --------------------

@vip_bp.route("/vip")
@login_required
def vip_page():
    """
    Страница VIP-участников.
    """
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    vip_data = load_vip_file(vip_file)

    return render_template(
        "vip.html",
        user=user,
        members=vip_data.items(),
        profile_key=profile_key
    )


# -------------------- AJAX: VIP DATA --------------------

@vip_bp.route("/vip_data")
@login_required
def vip_data():
    """
    Возвращает VIP-данные в JSON для панели.
    """
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    vip_data = load_vip_file(vip_file)

    return jsonify({"members": vip_data})
