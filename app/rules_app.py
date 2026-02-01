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
@rules_bp.route("/rules", methods=["POST"])
@login_required
def rules_modify():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    rules_file = CONFIG["profiles"][profile_key]["rules_file"]
    rules = load_rules(rules_file)

    # ---------- DELETE ----------
    if "delete_rule" in request.form:
        rule_id = request.form["delete_rule"]
        rules["rules"] = [r for r in rules["rules"] if r["id"] != rule_id]
        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    # ---------- EDIT ----------
    if "edit_rule" in request.form:
        rule_id = request.form["edit_rule"]

        for r in rules["rules"]:
            if r["id"] == rule_id:
                r["min"] = int(request.form["min"])
                r["max"] = int(request.form["max"])
                r["strength"] = int(request.form["strength"])
                r["duration"] = int(request.form["duration"])

                if request.form["action_type"] == "custom":
                    r["action"] = request.form["action"].strip()
                else:
                    r["action"] = None

        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    return redirect(url_for("rules.rules_page"))
@rules_bp.route("/test_rule/<int:index>", methods=["POST"])
@login_required
def test_rule(index):
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    rules_file = CONFIG["profiles"][profile_key]["rules_file"]
    rules = load_rules(rules_file).get("rules", [])

    if index < 0 or index >= len(rules):
        return {"status": "error", "message": "Правило не найдено"}

    rule = rules[index]

    from services.vibration_manager import enqueue_vibration

    if rule.get("action"):
        return {"status": "ok", "message": f"Действие: {rule['action']}"}

    strength = rule.get("strength", 1)
    duration = rule.get("duration", 5)

    enqueue_vibration(profile_key, strength, duration)

    return {"status": "ok", "message": f"Вибрация: сила={strength}, время={duration}s"}
