from flask import Blueprint, render_template, session, redirect, url_for, request
from functools import wraps
import json
import os
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

@stats_bp.route("/close_period", methods=["POST"])
@login_required
def close_period():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    # Пути к файлам из config.json
    profile_cfg = CONFIG["profiles"].get(profile_key)
    if not profile_cfg:
        return f"Профиль {profile_key} не найден", 500

    stats_file = profile_cfg["stats_file"]
    archive_file = f"data/stats/stats_archive_{profile_key}.json"

    # Загружаем текущую статистику
    stats = load_stats(stats_file)

    if not stats:
        return redirect(url_for("stats.stats_history"))

    # Загружаем архив
    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        archive = {"periods": []}

    # Определяем границы периода
    days_sorted = sorted(stats.keys())
    start_day = days_sorted[0]
    end_day = days_sorted[-1]

    # Считаем суммы
    total_income = 0
    total_vibrations = 0
    total_actions = 0
    total_other = 0
    total_archi_fee = 0

    for day, data in stats.items():
        total_income += data.get("net_income", 0)
        total_vibrations += data.get("vibrations", 0)
        total_actions += data.get("actions", 0)
        total_other += data.get("other", 0)
        total_archi_fee += data.get("archi_fee", 0)

    # Создаём новый период
    new_period = {
        "id": len(archive["periods"]) + 1,
        "start": start_day,
        "end": end_day,
        "total_income": total_income,
        "vibrations": total_vibrations,
        "actions": total_actions,
        "other": total_other,
        "archi_fee": total_archi_fee,
        "days": stats
    }

    archive["periods"].append(new_period)

    # Сохраняем архив
    tmp = archive_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, archive_file)

    # Очищаем текущую статистику
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump({}, f)

    return redirect(url_for("stats.stats_history"))

