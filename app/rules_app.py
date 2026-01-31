from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import uuid
import threading

from services.lovense_service import send_vibration_cloud
from config import CONFIG
from services.rules_service import load_rules, save_rules

rules_bp = Blueprint("rules", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- TEST VIBRATION --------------------

@rules_bp.route("/test_vibration", methods=["POST"])
@login_required
def test_vibration():
    """
    Тестовая вибрация для текущего профиля (private/public).
    """
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    def safe_vibration():
        try:
            send_vibration_cloud(CONFIG["profiles"][profile_key], 1, 5)
        except Exception as e:
            print(f"⚠️ Ошибка тестовой вибрации: {e}")

    threading.Thread(target=safe_vibration, daemon=True).start()

    return {"status": "ok", "message": "Вибрация отправлена ✅"}


# -------------------- RULES PAGE --------------------

@rules_bp.route("/rules", methods=["GET", "POST"])
@login_required
def rules_page():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    rules_file = CONFIG["profiles"][profile_key]["rules_file"]
    rules = load_rules(rules_file)

    if request.method == "POST" and "add_rule" in request.form:

        new_rule = {
            "id": str(uuid.uuid4()),
            "min": int(request.form["min"]),
            "max": int(request.form["max"]),
            "strength": int(request.form["strength"]),
            "duration": int(request.form["duration"]),
            "action": request.form.get("action") or None,
        }

        rules["rules"].append(new_rule)
        save_rules(rules_file, rules)

        return redirect(url_for("rules.rules_page"))

    return render_template(
        "rules.html",
        rules=rules["rules"],
        profile_key=profile_key
    )
