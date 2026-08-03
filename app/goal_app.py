from flask import Blueprint, request, session, jsonify, redirect, url_for
from functools import wraps

from services.goal_service import load_goal, save_goal
from app.ws_app import ws_send
from services.database import get_profile_by_key

goal_bp = Blueprint("goal", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- GET GOAL --------------------

@goal_bp.route("/goal_data")
@login_required
def goal_data():
    user = session["username"]
    mode = session.get("mode", "private")

    # ❗ В приватном режиме цели нет
    if mode == "private":
        return {"title": "", "target": 0, "current": 0}

    profile_key = f"{user}_{mode}"
    profile = get_profile_by_key(profile_key)

    if not profile:
        return {"title": "", "target": 0, "current": 0}

    return load_goal(profile_key)


# -------------------- CREATE NEW GOAL --------------------

@goal_bp.route("/goal_new", methods=["POST"])
@login_required
def goal_new():
    user = session["username"]
    mode = session.get("mode", "private")

    if mode == "private":
        return {"status": "error", "message": "В приватном режиме цели нет"}

    profile_key = f"{user}_{mode}"
    profile = get_profile_by_key(profile_key)

    if not profile:
        return {"status": "error", "message": "Профиль не найден"}

    title = request.form.get("title", "")
    target = int(request.form.get("target", 0))

    goal = {
        "title": title,
        "target": target,
        "current": 0
    }

    save_goal(profile_key, goal)

    ws_send(
        {"goal_update": True, "goal": goal},
        role="panel",
        profile_key=profile_key
    )

    return {"status": "ok"}


# -------------------- AUTO UPDATE GOAL (DONATION) --------------------

def goal_add_points(user: str, amount: float):
    mode = "public"
    profile_key = f"{user}_{mode}"
    profile = get_profile_by_key(profile_key)

    if not profile:
        return

    goal = load_goal(profile_key)

    if goal["target"] <= 0:
        return

    goal["current"] += amount

    if goal["current"] > goal["target"]:
        goal["current"] = goal["target"]

    save_goal(profile_key, goal)

    ws_send(
        {"goal_update": True, "goal": goal},
        role="panel",
        profile_key=profile_key
    )


# -------------------- RESET GOAL --------------------

@goal_bp.route("/goal_reset", methods=["POST"])
@login_required
def goal_reset():
    user = session["username"]
    mode = session.get("mode", "private")

    if mode == "private":
        return {"status": "error", "message": "В приватном режиме цели нет"}

    profile_key = f"{user}_{mode}"
    profile = get_profile_by_key(profile_key)

    if not profile:
        return {"status": "error", "message": "Профиль не найден"}

    goal = load_goal(profile_key)
    goal["current"] = 0

    save_goal(profile_key, goal)

    ws_send(
        {"goal_update": True, "goal": goal},
        role="panel",
        profile_key=profile_key
    )

    return {"status": "ok"}
