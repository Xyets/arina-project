from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import uuid
import os
from werkzeug.utils import secure_filename

from config import CONFIG
from services.reactions_service import load_reaction_rules, save_reaction_rules

reactions_bp = Blueprint("reactions", __name__)

# Путь к папке реакций — берём из CONFIG
STATIC_REACTIONS_DIR = CONFIG["static_reactions_dir"]


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- REACTIONS PAGE --------------------

@reactions_bp.route("/reactions", methods=["GET", "POST"])
@login_required
def reactions_page():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    # путь к файлу реакций из config.json
    reactions_file = CONFIG["profiles"][profile_key]["reactions_file"]

    # загрузка правил
    rules = load_reaction_rules(reactions_file)

    # ⭐ сортировка правил
    rules["rules"].sort(key=lambda r: r.get("min_points", 0))

    # -------------------- ДОБАВЛЕНИЕ ПРАВИЛА --------------------
    if request.method == "POST" and "add_reaction_rule" in request.form:

        new_rule = {
            "id": str(uuid.uuid4()),
            "min_points": int(request.form["min_points"]),
            "max_points": int(request.form["max_points"]),
            "duration": int(request.form["duration"]),
            "image": None
        }

        file = request.files.get("image")
        if file and file.filename:
            safe_name = secure_filename(file.filename)
            filename = f"{profile_key}_{uuid.uuid4()}_{safe_name}"
            full_path = os.path.join(STATIC_REACTIONS_DIR, filename)

            os.makedirs(STATIC_REACTIONS_DIR, exist_ok=True)
            file.save(full_path)

            new_rule["image"] = f"reactions/{filename}"

        rules["rules"].append(new_rule)
        save_reaction_rules(reactions_file, rules)

        return redirect(url_for("reactions.reactions_page"))

    # -------------------- УДАЛЕНИЕ ПРАВИЛА --------------------
    if request.method == "POST" and "delete_reaction_rule" in request.form:
        rule_id = request.form["delete_reaction_rule"]

        rules["rules"] = [r for r in rules["rules"] if r["id"] != rule_id]
        save_reaction_rules(reactions_file, rules)

        return redirect(url_for("reactions.reactions_page"))

    # -------------------- РЕДАКТИРОВАНИЕ ПРАВИЛА --------------------
    if request.method == "POST" and "edit_reaction_rule" in request.form:
        rule_id = request.form["edit_reaction_rule"]

        for rule in rules["rules"]:
            if rule["id"] == rule_id:
                rule["min_points"] = int(request.form["min_points"])
                rule["max_points"] = int(request.form["max_points"])
                rule["duration"] = int(request.form["duration"])

                file = request.files.get("image")
                if file and file.filename:
                    safe_name = secure_filename(file.filename)
                    filename = f"{profile_key}_{uuid.uuid4()}_{safe_name}"
                    full_path = os.path.join(STATIC_REACTIONS_DIR, filename)

                    os.makedirs(STATIC_REACTIONS_DIR, exist_ok=True)
                    file.save(full_path)

                    rule["image"] = f"reactions/{filename}"

                break

        save_reaction_rules(reactions_file, rules)
        return redirect(url_for("reactions.reactions_page"))

    # -------------------- РЕНДЕР --------------------
    return render_template(
        "reactions.html",
        reactions=rules,
        profile_key=profile_key,
        profile=CONFIG["profiles"][profile_key]
    )
