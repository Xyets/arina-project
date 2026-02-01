from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from functools import wraps
from datetime import datetime

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


# -------------------- REMOVE MEMBER --------------------

@vip_bp.route("/remove_member", methods=["POST"])
@login_required
def remove_member():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    user_id = request.form.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Нет user_id"}, 400

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    vip_data = load_vip_file(vip_file)

    if user_id in vip_data:
        del vip_data[user_id]
        save_vip_file(vip_file, vip_data)
        return {"status": "ok", "message": "Мембер удалён"}

    return {"status": "error", "message": "Мембер не найден"}, 404


# -------------------- VIP PAGE --------------------

@vip_bp.route("/vip", methods=["GET", "POST"])
@login_required
def vip_page():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    vip_data = load_vip_file(vip_file)

    # ---------- SAVE MEMBER ----------
    if request.method == "POST" and "user_id" in request.form:
        user_id = request.form.get("user_id")

        if user_id in vip_data:
            vip_data[user_id]["name"] = request.form.get("name", "").strip()
            vip_data[user_id]["notes"] = request.form.get("notes", "").strip()
            save_vip_file(vip_file, vip_data)

        sort_by = request.form.get("sort", "total")
        query = request.form.get("q", "")
        return redirect(url_for("vip.vip_page", sort=sort_by, q=query))

    # ---------- FILTER ----------
    query = request.args.get("q", "").strip().lower()
    filtered = {
        uid: info for uid, info in vip_data.items()
        if not query
        or query in uid.lower()
        or query in info.get("name", "").lower()
        or query in info.get("notes", "").lower()
    }

    # ---------- SORT ----------
    sort_by = request.args.get("sort", "total")

    def parse_date(s: str):
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return datetime.min

    if sort_by == "last_login":
        sorted_members = sorted(
            filtered.items(),
            key=lambda x: parse_date(x[1].get("last_login", "")),
            reverse=True,
        )
    else:
        sorted_members = sorted(
            filtered.items(),
            key=lambda x: x[1].get(sort_by, 0),
            reverse=True
        )

    return render_template(
        "vip.html",
        user=user,
        members=sorted_members,
        query=query
    )


# -------------------- AJAX VIP DATA --------------------

@vip_bp.route("/vip_data")
@login_required
def vip_data():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    vip_file = CONFIG["profiles"][profile_key]["vip_file"]
    vip_data = load_vip_file(vip_file)

    return {"members": vip_data}
