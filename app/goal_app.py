from flask import Blueprint, request, session, jsonify, redirect, url_for
from functools import wraps

from config import CONFIG
from services.goal_service import load_goal, save_goal
from app.ws_app import ws_send

goal_bp = Blueprint("goal", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- GOAL DATA --------------------

@goal_bp.route("/goal_data")
@login_required
def goal_data():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    # путь к файлу цели
    goal_file = CONFIG["profiles"][profile_key]["goal_file"]

    return load_goal(goal_file)


# -------------------- CREATE NEW GOAL --------------------

@goal_bp.route("/goal_new", methods=["POST"])
@login_required
def goal_new():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    # путь к файлу цели
    goal_file = CONFIG["profiles"][profile_key]["goal_file"]

    title = request.form.get("title", "")
    target = int(request.form.get("target", 0))

    goal = {
        "title": title,
        "target": target,
        "current": 0
    }

    save_goal(goal_file, goal)

    # уведомляем OBS/панель
    ws_send(
        {"goal_update": True, "goal": goal},
        role="panel",
        user=user
    )

    return {"status": "ok"}
