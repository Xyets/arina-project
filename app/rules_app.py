from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import uuid
import json
import asyncio
import websockets

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


# -------------------- WS SEND --------------------

async def send_ws_vibration(profile_key, strength, duration):
    async with websockets.connect("ws://127.0.0.1:8765") as ws:
        await ws.send(json.dumps({
            "type": "vibration",
            "profile_key": profile_key,
            "strength": strength,
            "duration": duration
        }))


# -------------------- TEST VIBRATION --------------------

@rules_bp.route("/test_vibration", methods=["POST"])
@login_required
def test_vibration():
    user = session["user"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    asyncio.run(send_ws_vibration(profile_key, 1, 5))

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

    if rule.get("type") == "custom":
        return {"status": "ok", "message": f"Действие: {rule['action']}"}

    if rule.get("type") == "wheel":
        segments = rule.get("segments", [])
        if not segments:
            return {"status": "error", "message": "Нет сегментов"}

        import random
        winner_index = random.randint(0, len(segments) - 1)
        winner = segments[winner_index]

        # отправляем команду OBS запустить колесо
        from ws_app import ws_send
        ws_send({
            "type": "wheel_spin",
            "profile": profile_key,
            "segments": segments,
            "winner_index": winner_index,
            "action": winner["action"]
        }, role="obs", profile_key=profile_key)

        return {"status": "ok", "message": f"Колесо запущено! Выпал сегмент: {winner['name']}"}


    asyncio.run(send_ws_vibration(profile_key, rule["strength"], rule["duration"]))

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

    # ADD
    if request.method == "POST" and "add_rule" in request.form:
        action_type = request.form.get("action_type")

        new_rule = {
            "id": str(uuid.uuid4()),
            "min": int(request.form["min"]),
            "max": int(request.form["max"]),
            "strength": int(request.form["strength"]),
            "duration": int(request.form["duration"]),
            "type": action_type,
            "action": None
        }

        # Вибрация
        if action_type == "vibration":
            new_rule["action"] = None

        # Кастомное действие
        elif action_type == "custom":
            new_rule["action"] = request.form["action"].strip() or None

        # Колесо фортуны
        elif action_type == "wheel":
            new_rule["segments"] = []   # пока пусто

        rules["rules"].append(new_rule)
        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    # DELETE
    if request.method == "POST" and "delete_rule" in request.form:
        rule_id = request.form["delete_rule"]
        rules["rules"] = [r for r in rules["rules"] if r["id"] != rule_id]
        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    # EDIT
    if request.method == "POST" and "edit_rule" in request.form:
        rule_id = request.form["edit_rule"]

        for r in rules["rules"]:
            if r["id"] == rule_id:
                r["min"] = int(request.form["min"])
                r["max"] = int(request.form["max"])
                r["strength"] = int(request.form["strength"])
                r["duration"] = int(request.form["duration"])

                action_type = request.form.get("action_type")
                r["type"] = action_type

                # Вибрация
                if action_type == "vibration":
                    r["action"] = None

                # Кастомное действие
                elif action_type == "custom":
                    r["action"] = request.form["action"].strip() or None

                # Колесо фортуны
                elif action_type == "wheel":
                    r["action"] = None
                    if "segments" not in r:
                        r["segments"] = []


        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    # ADD SEGMENT
    if request.method == "POST" and "add_segment" in request.form:
        rule_id = request.form["add_segment"]

        for r in rules["rules"]:
            if r["id"] == rule_id:
                if "segments" not in r:
                    r["segments"] = []

                r["segments"].append({
                    "name": request.form["seg_name"],
                    "chance": int(request.form["seg_chance"]),
                    "action": request.form["seg_action"]
                })

        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))
    # DELETE SEGMENT
    if request.method == "POST" and "delete_segment" in request.form:
        rule_id = request.form["delete_segment"]
        seg_index = int(request.form["seg_index"])

        for r in rules["rules"]:
            if r["id"] == rule_id and "segments" in r:
                if 0 <= seg_index < len(r["segments"]):
                    r["segments"].pop(seg_index)

        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    return render_template(
        "rules.html",
        rules=rules["rules"],
        profile_key=profile_key
    )
