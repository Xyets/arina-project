from flask import Blueprint, request, session, jsonify, redirect, url_for
from services.goal_service import load_goal, save_goal
from app.ws_app import ws_send
from config import CONFIG
from functools import wraps

goal_bp = Blueprint("goal", __name__)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


@goal_bp.route("/goal_data")
@login_required
def goal_data():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    return load_goal(profile_key)


@goal_bp.route("/goal_new", methods=["POST"])
@login_required
def goal_new():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    title = request.form.get("title", "")
    target = int(request.form.get("target", 0))

    goal = {"title": title, "target": target, "current": 0}
    save_goal(profile_key, goal)

    ws_send(
        {"goal_update": True, "goal": goal},
        role="panel",
        user=user
    )

    return {"status": "ok"}
