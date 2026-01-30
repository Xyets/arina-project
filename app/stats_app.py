from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps

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


# -------------------- STATS PAGE --------------------

@stats_bp.route("/stats")
@login_required
def stats_page():
    """
    Страница статистики.
    Загружает сырые данные и вычисляет агрегированную статистику.
    """
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    stats_data = load_stats(profile_key)
    results, summary = calculate_stats(stats_data, user=user)

    return render_template(
        "stats.html",
        user=user,
        results=results,
        summary=summary,
        profile_key=profile_key
    )
