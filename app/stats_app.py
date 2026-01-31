from flask import Blueprint, render_template, session, redirect, url_for, request
from functools import wraps
import json

from config import CONFIG
from services.stats_service import load_stats, calculate_stats

stats_bp = Blueprint("stats", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- СТРАНИЦА СТАТИСТИКИ --------------------

@stats_bp.route("/stats")
@login_required
def stats_page():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    profile_cfg = CONFIG["profiles"].get(profile_key)
    if not profile_cfg:
        return f"Профиль {profile_key} не найден", 500

    stats_file = profile_cfg.get("stats_file")
    stats_data = load_stats(stats_file)
    results, summary = calculate_stats(stats_data, user=user)

    return render_template(
        "stats.html",
        user=user,
        results=results,
        summary=summary,
        profile_key=profile_key
    )


# -------------------- ИСТОРИЯ СТАТИСТИКИ --------------------

@stats_bp.route("/stats_history")
@login_required
def stats_history():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    archive_file = f"data/stats/stats_archive_{profile_key}.json"

    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        archive = {"periods": []}

    from_date = request.args.get("from")
    to_date = request.args.get("to")

    if from_date and to_date:
        filtered = []
        for p in archive.get("periods", []):
            if p.get("start") >= from_date and p.get("end") <= to_date:
                filtered.append(p)
        archive = {"periods": filtered}

    return render_template(
        "stats_history.html",
        user=user,
        archive=archive
    )
