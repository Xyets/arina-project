from flask import Blueprint, request, render_template, session, redirect, url_for, jsonify
from functools import wraps
import uuid
import os
import json
from werkzeug.utils import secure_filename

from services.reactions_service import load_reaction_rules, save_reaction_rules
from services.redis_client import redis_client
from services.database import get_profile_by_key

reactions_bp = Blueprint("reactions", __name__)

# Папка для хранения изображений реакций
STATIC_REACTIONS_DIR = os.path.join("static", "reactions")


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper


# -------------------- REACTIONS PAGE --------------------

@reactions_bp.route("/reactions", methods=["GET", "POST"])
@login_required
def reactions_page():
    user = session["username"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    profile = get_profile_by_key(profile_key)
    if not profile:
        return "Профиль не найден", 404

    # Загружаем правила реакций по profile_key
    rules = load_reaction_rules(profile_key)
    rules["rules"].sort(key=lambda r: r.get("min_points", 0))

    # ADD RULE
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
        save_reaction_rules(profile_key, rules)

        return redirect(url_for("reactions.reactions_page"))

    # DELETE RULE
    if request.method == "POST" and "delete_reaction_rule" in request.form:
        rule_id = request.form["delete_reaction_rule"]
        rules["rules"] = [r for r in rules["rules"] if r["id"] != rule_id]
        save_reaction_rules(profile_key, rules)
        return redirect(url_for("reactions.reactions_page"))

    # EDIT RULE
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

        save_reaction_rules(profile_key, rules)
        return redirect(url_for("reactions.reactions_page"))

    return render_template(
        "reactions.html",
        reactions=rules,
        profile_key=profile_key,
        profile=profile,
        user=user,
        mode=mode,
    )


# -------------------- TEST REACTION --------------------

@reactions_bp.route("/test_reaction", methods=["POST"])
@login_required
def test_reaction():
    data = request.get_json()
    rule_id = data.get("rule_id")
    profile_key = data.get("profile_key")

    if not rule_id or not profile_key:
        return jsonify({"status": "error", "message": "missing params"}), 400

    profile = get_profile_by_key(profile_key)
    if not profile:
        return jsonify({"status": "error", "message": "profile not found"}), 404

    # Загружаем правила реакций по profile_key
    rules = load_reaction_rules(profile_key)["rules"]

    rule = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        return jsonify({"status": "error", "message": "rule not found"}), 404

    redis_client.publish("obs_reactions", json.dumps({
        "reaction": {
            "image": rule["image"],
            "duration": rule["duration"]
        },
        "profile": profile_key
    }))

    return jsonify({"status": "ok"})
