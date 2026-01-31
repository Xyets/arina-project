from flask import Blueprint, render_template, abort
from config import CONFIG

obs_bp = Blueprint("obs", __name__)


@obs_bp.route("/obs_alert/<user>/<mode>")
def obs_alert(user, mode):
    """
    Универсальная OBS-страница:
    /obs_alert/Arina/private
    /obs_alert/Arina/public
    /obs_alert/Irina/private
    /obs_alert/Irina/public
    """

    # Проверяем корректность режима
    if mode not in ("private", "public"):
        return abort(404)

    # Формируем ключ профиля
    profile_key = f"{user}_{mode}"

    # Проверяем, что профиль существует
    if profile_key not in CONFIG["profiles"]:
        return abort(404)

    # Выбираем правильный шаблон
    template_name = f"obs_alert_{user.lower()}.html"

    return render_template(template_name, profile_key=profile_key)
