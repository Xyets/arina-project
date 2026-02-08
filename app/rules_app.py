from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import uuid
from services.vibration_manager import vibration_queues

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
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    vibration_queues[profile_key].put_nowait((1, 5))

    return {"status": "ok", "message": "Вибрация отправлена ✅"}


# -------------------- TEST SPECIFIC RULE --------------------

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

    if rule.get("action"):
        return {"status": "ok", "message": f"Действие: {rule['action']}"}

    # ✔ вот правильная строка
    vibration_queues[profile_key].put_nowait((rule["strength"], rule["duration"]))

    return {"status": "ok", "message": "Вибрация отправлена по правилу"}


# -------------------- RULES PAGE --------------------

@rules_bp.route("/rules", methods=["GET", "POST"])
@login_required
def rules_page():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    rules_file = CONFIG["profiles"][profile_key]["rules_file"]
    rules = load_rules(rules_file)

    # ---------- ADD ----------
    if request.method == "POST" and "add_rule" in request.form:
        new_rule = {
            "id": str(uuid.uuid4()),
            "min": int(request.form["min"]),
            "max": int(request.form["max"]),
            "strength": int(request.form["strength"]),
            "duration": int(request.form["duration"]),
            "action": request.form["action"].strip() or None,
        }
        rules["rules"].append(new_rule)
        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    # ---------- DELETE ----------
    if request.method == "POST" and "delete_rule" in request.form:
        rule_id = request.form["delete_rule"]
        rules["rules"] = [r for r in rules["rules"] if r["id"] != rule_id]
        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    # ---------- EDIT ----------
    if request.method == "POST" and "edit_rule" in request.form:
        rule_id = request.form["edit_rule"]

        for r in rules["rules"]:
            if r["id"] == rule_id:
                r["min"] = int(request.form["min"])
                r["max"] = int(request.form["max"])
                r["strength"] = int(request.form["strength"])
                r["duration"] = int(request.form["duration"])

                action_type = request.form.get("action_type")

                if action_type == "vibration":
                    r["action"] = None
                else:
                    r["action"] = request.form["action"].strip() or None

        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    return render_template(
        "rules.html",
        rules=rules["rules"],
        profile_key=profile_key
    )
