from flask import Blueprint, render_template, abort
from services.database import get_profile_by_key

obs_bp = Blueprint(
    "obs",
    __name__,
    static_folder="static_obs",
    static_url_path="/obs_static"
)

# -------------------- OBS ALERT --------------------

@obs_bp.route("/obs_alert/<user>/<mode>")
def obs_alert(user, mode):
    if mode not in ("private", "public"):
        return abort(404)

    profile_key = f"{user}_{mode}"
    profile = get_profile_by_key(profile_key)

    if not profile:
        return abort(404)

    return render_template("obs_alert.html", profile_key=profile_key)


# -------------------- OBS REACTIONS --------------------

@obs_bp.route("/obs_reactions/<user>/<mode>")
def obs_reactions(user, mode):
    if mode not in ("private", "public"):
        return abort(404)

    profile_key = f"{user}_{mode}"
    profile = get_profile_by_key(profile_key)

    if not profile:
        return abort(404)

    return render_template("obs_reactions.html", profile_key=profile_key)


# -------------------- OBS GOAL --------------------

@obs_bp.route("/obs_goal/<user>/<mode>")
def obs_goal(user, mode):
    if mode not in ("private", "public"):
        return abort(404)

    profile_key = f"{user}_{mode}"
    profile = get_profile_by_key(profile_key)

    if not profile:
        return abort(404)

    # Автоматический выбор шаблона по имени модели
    username = user.lower()

    if username == "arina":
        return render_template("obs_goal_arina.html", profile_key=profile_key)
    else:
        return render_template("obs_goal_irina.html", profile_key=profile_key)


# -------------------- OBS WHEEL --------------------

@obs_bp.route("/obs_wheel/<user>/<mode>")
def obs_wheel(user, mode):
    if mode not in ("private", "public"):
        return abort(404)

    profile_key = f"{user}_{mode}"
    profile = get_profile_by_key(profile_key)

    if not profile:
        return abort(404)

    return render_template("obs_wheel.html", profile_key=profile_key)
