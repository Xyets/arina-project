from flask import Blueprint, render_template, abort
from config import CONFIG

obs_bp = Blueprint(
    "obs",
    __name__,
    static_folder="static_obs",
    static_url_path="/obs_static"
)



@obs_bp.route("/obs_alert/<user>/<mode>")
def obs_alert(user, mode):
    if mode not in ("private", "public"):
        return abort(404)

    profile_key = f"{user}_{mode}"

    if profile_key not in CONFIG["profiles"]:
        return abort(404)

    return render_template("obs_alert.html", profile_key=profile_key)


@obs_bp.route("/obs_reactions/<user>/<mode>")
def obs_reactions(user, mode):
    if mode not in ("private", "public"):
        return abort(404)

    profile_key = f"{user}_{mode}"

    if profile_key not in CONFIG["profiles"]:
        return abort(404)

    return render_template("obs_reactions.html", profile_key=profile_key)



@obs_bp.route("/obs_goal/<user>/<mode>")
def obs_goal(user, mode):
    if mode not in ("private", "public"):
        return abort(404)

    profile_key = f"{user}_{mode}"

    if profile_key not in CONFIG["profiles"]:
        return abort(404)

    # Выбор шаблона по имени пользователя
    if user.lower() == "arina":
        return render_template("obs_goal_arina.html", profile_key=profile_key)
    else:
        return render_template("obs_goal_irina.html", profile_key=profile_key)