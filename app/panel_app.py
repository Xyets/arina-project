from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps

from config import CONFIG
from services.logs_service import load_logs_from_file, clear_logs_file
from services.goal_service import load_goal
from services.audit import audit_event
from services.redis_client import redis_client   # ← правильный импорт

panel_bp = Blueprint("panel", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


@panel_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()

        users_cfg = CONFIG.get("USERS", {})

        user_key = None
        for u in users_cfg:
            if u.lower() == user.lower():
                user_key = u
                break

        if user_key and users_cfg.get(user_key) == pwd:
            session["user"] = user_key
            session["mode"] = "private"

            profile_key = f"{user_key}_private"
            audit_event(profile_key, "auth", {"type": "login"})

            return redirect(url_for("panel.index"))

        return render_template("login.html", error="Неверный логин или пароль")

    return render_template("login.html")


@panel_bp.route("/logout")
def logout():
    user = session.get("user")
    mode = session.get("mode", "private")

    if user:
        profile_key = f"{user}_{mode}"
        audit_event(profile_key, mode, {"type": "logout"})

    session.clear()
    return redirect(url_for("panel.login"))


# -------------------- ПАНЕЛЬ --------------------

@panel_bp.route("/")
@login_required
def index():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    profile = CONFIG["profiles"][profile_key]
    logs = load_logs_from_file(profile_key)

    goal_file = CONFIG["profiles"][profile_key]["goal_file"]
    goal = load_goal(goal_file)

    return render_template(
        "index.html",
        user=user,
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

    redis_client.hset("user_modes", session["user"], mode)

    return {"status": "ok", "mode": mode}


# -------------------- AJAX: логи --------------------

@panel_bp.route("/logs_data")
@login_required
def logs_data():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    logs = load_logs_from_file(profile_key)
    return jsonify({"logs": logs})


@panel_bp.route("/clear_logs", methods=["POST"])
@login_required
def clear_logs():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    clear_logs_file(profile_key)
    return {"status": "ok"}
