from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps

from services.database import get_model_by_username, get_connection
from services.logs_service import load_logs_from_file, clear_logs_file
from services.goal_service import load_goal
from services.audit import audit_event
from services.redis_client import redis_client

panel_bp = Blueprint("panel", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


def get_profile_from_db(username, mode):
    conn = get_connection()
    cur = conn.cursor()
    profile_key = f"{username}_{mode}"
    cur.execute("SELECT * FROM profiles WHERE profile_key = ?", (profile_key,))
    row = cur.fetchone()
    conn.close()
    return row


@panel_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()

        model = get_model_by_username(username)

        if not model:
            return render_template("login.html", error="Неверный логин или пароль")

        if model["password_hash"] != pwd:
            return render_template("login.html", error="Неверный логин или пароль")

        session["user_id"] = model["id"]
        session["username"] = model["username"]
        session["mode"] = "private"

        return redirect(url_for("panel.index"))

    return render_template("login.html")


@panel_bp.route("/logout")
def logout():
    username = session.get("username")
    mode = session.get("mode", "private")

    if username:
        profile_key = f"{username}_{mode}"
        audit_event(profile_key, "logout")   # ✔ исправлено

    session.clear()
    return redirect(url_for("panel.login"))   # ✔ теперь работает


# -------------------- ПАНЕЛЬ --------------------

@panel_bp.route("/")
@login_required
def index():
    username = session["username"]
    mode = session.get("mode", "private")

    profile = get_profile_from_db(username, mode)
    if not profile:
        return "Профиль не найден", 404

    profile_key = profile["profile_key"]

    logs = load_logs_from_file(profile_key)
    goal = load_goal(profile_key)

    return render_template(
        "index.html",
        user=username,
        profile=profile,
        logs=logs,
        current_mode=mode,
        goal=goal,
        current_profile=profile_key
    )


# -------------------- AJAX: смена режима --------------------

@panel_bp.route("/set_mode", methods=["POST"])
@login_required
def set_mode():
    data = request.get_json()
    mode = data.get("mode")

    if mode not in ("public", "private"):
        return {"status": "error", "message": "Неверный режим"}

    session["mode"] = mode
    redis_client.hset("user_modes", session["username"], mode)

    return {"status": "ok", "mode": mode}


# -------------------- AJAX: логи --------------------

@panel_bp.route("/logs_data")
@login_required
def logs_data():
    username = session["username"]
    mode = session.get("mode", "private")

    profile = get_profile_from_db(username, mode)
    if not profile:
        return jsonify({"logs": []})

    logs = load_logs_from_file(profile["profile_key"])
    return jsonify({"logs": logs})


@panel_bp.route("/clear_logs", methods=["POST"])
@login_required
def clear_logs():
    username = session["username"]
    mode = session.get("mode", "private")

    profile = get_profile_from_db(username, mode)
    if not profile:
        return {"status": "error"}

    clear_logs_file(profile["profile_key"])
    return {"status": "ok"}
