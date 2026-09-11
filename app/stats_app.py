from flask import Blueprint, render_template, session, redirect, url_for, request
from functools import wraps
import json
import os
from datetime import datetime

from services.stats_service import load_stats, calculate_stats
from services.database import get_profile_by_key

stats_bp = Blueprint("stats", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- СТРАНИЦА СТАТИСТИКИ --------------------

@stats_bp.route("/stats")
@login_required
def stats_page():
    user = session["username"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    profile = get_profile_by_key(profile_key)
    if not profile:
        return f"Профиль {profile_key} не найден", 500

    stats_data = load_stats(profile_key)

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
    user = session["username"]
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
        archive["periods"] = [
            p for p in archive.get("periods", [])
            if p.get("start") >= from_date and p.get("end") <= to_date
        ]

    return render_template(
        "stats_history.html",
        user=user,
        archive=archive
    )


# -------------------- ЗАКРЫТИЕ ПЕРИОДА --------------------

@stats_bp.route("/close_period", methods=["POST"])
@login_required
def close_period():
    user = session["username"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    # Загружаем профиль
    profile = get_profile_by_key(profile_key)
    if not profile:
        return "Профиль не найден", 500

    stats_file = profile["stats_file"]
    archive_file = f"data/stats/stats_archive_{profile_key}.json"

    # Загружаем текущую статистику
    stats = load_stats(profile_key)
    if not stats:
        return redirect(url_for("stats.stats_history"))

    # Получаем диапазон дат
    data = request.get_json()
    start = data.get("start")
    end = data.get("end")

    if not start or not end:
        return "Неверный диапазон дат", 400

    # Фильтруем дни
    selected_days = {
        day: info for day, info in stats.items()
        if start <= day <= end
    }

    if not selected_days:
        return "Нет данных в выбранном диапазоне", 400

    # Загружаем архив
    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except:
        archive = {"periods": []}

    # Итоги
    total_vibr = sum(float(d.get("vibrations", 0)) for d in selected_days.values())
    total_act = sum(float(d.get("actions", 0)) for d in selected_days.values())
    total_other = sum(float(d.get("other", 0)) for d in selected_days.values())
    total_points = sum(float(d.get("total", 0)) for d in selected_days.values())

    # ARCHI только для Irina
    if user.lower() == "irina":
        total_archi = sum(float(d.get("vibrations", 0)) * 0.7 * 0.1 for d in selected_days.values())
    else:
        total_archi = 0

    total_income = total_points * 0.7 - total_archi

    # Создаём период
    new_period = {
        "id": len(archive["periods"]) + 1,
        "start": start,
        "end": end,
        "vibrations": total_vibr,
        "actions": total_act,
        "other": total_other,
        "total_points": total_points,
        "archi_fee": total_archi,
        "total_income": total_income,
        "days": selected_days
    }

    archive["periods"].append(new_period)

    # Сохраняем архив
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)

    # Удаляем закрытые дни из текущей статистики
    remaining_days = {
        day: info for day, info in stats.items()
        if day < start or day > end
    }

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(remaining_days, f, indent=2, ensure_ascii=False)

    return redirect(url_for("stats.stats_history"))
# -------------------- НОВАЯ СТРАНИЦА СТАТИСТИКИ (SPA) --------------------

@stats_bp.route("/stats_beta")
@login_required
def stats_beta_page():
    user = session["username"]          # кто смотрит страницу
    mode = session.get("mode", "private")

    # список моделей
    models = ["Irina", "Arina"]

    # выбранная модель
    model = request.args.get("model", user)

    # ключ профиля выбранной модели
    profile_key = f"{model}_{mode}"

    profile = get_profile_by_key(profile_key)
    if not profile:
        return f"Профиль {profile_key} не найден", 500

    # загружаем статистику выбранной модели
    stats_data = load_stats(profile_key)

    # считаем статистику выбранной модели
    results, summary = calculate_stats(stats_data, user=model)

    # можно ли закрывать период?
    can_close_period = (user == model)

    return render_template(
        "stats_beta.html",
        user=user,
        model=model,
        models=models,
        results=results,
        summary=summary,
        profile_key=profile_key,
        mode=mode,
        can_close_period=can_close_period
    )

