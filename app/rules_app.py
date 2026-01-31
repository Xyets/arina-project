from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import uuid

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


# -------------------- RULES PAGE --------------------

@rules_bp.route("/rules", methods=["GET", "POST"])
@login_required
def rules_page():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    # путь к файлу правил из config.json
    rules_file = CONFIG["profiles"][profile_key]["rules_file"]

    # загрузка правил
    rules = load_rules(rules_file)

    # Добавление нового правила
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
