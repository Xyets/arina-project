from flask import Blueprint, request, render_template, session, redirect, url_for
from functools import wraps
import uuid
import json
import asyncio
import websockets

from services.rules_service import load_rules, save_rules
from services.database import get_profile_by_key

rules_bp = Blueprint("rules", __name__)


# -------------------- AUTH --------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
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


async def send_ws_wheel_spin(profile_key, segments):
    async with websockets.connect("ws://127.0.0.1:8765") as ws:
        await ws.send(json.dumps({
            "type": "wheel_spin",
            "profile": profile_key,
            "segments": segments
        }))


# -------------------- TEST VIBRATION --------------------

@rules_bp.route("/test_vibration", methods=["POST"])
@login_required
def test_vibration():
    user = session["username"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    asyncio.run(send_ws_vibration(profile_key, 1, 5))

    return {"status": "ok", "message": "Вибрация отправлена ✅"}


# -------------------- TEST SPECIFIC RULE --------------------

@rules_bp.route("/test_rule/<int:index>", methods=["POST"])
@login_required
def test_rule(index):
    user = session["username"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"

    profile = get_profile_by_key(profile_key)
    if not profile:
        return {"status": "error", "message": "Профиль не найден"}

    # Читаем путь к файлу правил из БД
    rules_file = profile["rules_file"]
    rules = load_rules(rules_file).get("rules", [])

    if index < 0 or index >= len(rules):
        return {"status": "error", "message": "Правило не найдено"}

    rule = rules[index]

    # CUSTOM
    if rule.get("type") == "custom":
        return {"status": "ok", "message": f"Действие: {rule['action']}"}

    # WHEEL
    if rule.get("type") == "wheel":
        segments = rule.get("segments", [])
        if not segments:
            return {"status": "error", "message": "Нет сегментов"}

        asyncio.run(send_ws_wheel_spin(profile_key, segments))
        return {"status": "ok", "message": "Колесо запущено!"}

    # VIBRATION
    if rule.get("type") == "vibration":
        strength = int(rule.get("strength", 1))
        duration = int(rule.get("duration", 5))

        asyncio.run(send_ws_vibration(profile_key, strength, duration))
        return {"status": "ok", "message": "Вибрация отправлена"}

    return {"status": "error", "message": "Неизвестный тип правила"}


# -------------------- RULES PAGE --------------------

@rules_bp.route("/rules", methods=["GET", "POST"])
@login_required
def rules_page():
    user = session["username"]
    mode = session.get("mode", "private")
    profile_key = f"{user}_{mode}"
    # ================= DEBUG LOGS =================
    print("========== RULES DEBUG ==========")
    print(f"[RULES DEBUG] profile_key={profile_key}")
    print(f"[RULES DEBUG] rules_file_from_db={profile['rules_file']}")
    print(f"[RULES DEBUG] file_exists={os.path.exists(profile['rules_file'])}")
    print(f"[RULES DEBUG] full_path={os.path.abspath(profile['rules_file'])}")

    try:
        with open(profile["rules_file"], "r", encoding="utf-8") as f:
            print("[RULES DEBUG] file_content_preview=", f.read()[:200])
    except Exception as e:
        print("[RULES DEBUG] ERROR reading file:", e)

    print("=================================")
    # ==============================================

    profile = get_profile_by_key(profile_key)
    if not profile:
        return "Профиль не найден", 404

    # Читаем путь к файлу правил из БД
    rules_file = profile["rules_file"]
    rules = load_rules(rules_file)

    # ADD RULE
    if request.method == "POST" and "add_rule" in request.form:
        action_type = request.form.get("action_type")

        new_rule = {
            "id": str(uuid.uuid4()),
            "min": int(request.form["min"]),
            "max": int(request.form["max"]),
            "strength": int(request.form["strength"] or 0),
            "duration": int(request.form["duration"] or 0),
            "type": action_type,
            "action": None
        }

        if action_type == "vibration":
            new_rule["action"] = None

        elif action_type == "custom":
            new_rule["action"] = request.form["action"].strip() or None

        elif action_type == "wheel":
            new_rule["action"] = "wheel"
            new_rule["segments"] = []

        rules["rules"].append(new_rule)
        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    # DELETE RULE
    if request.method == "POST" and "delete_rule" in request.form:
        rule_id = request.form["delete_rule"]
        rules["rules"] = [r for r in rules["rules"] if r["id"] != rule_id]
        save_rules(rules_file, rules)
        return redirect(url_for("rules.rules_page"))

    # EDIT RULE
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

                if action_type == "vibration":
                    r["action"] = None

                elif action_type == "custom":
                    r["action"] = request.form["action"].strip() or None

                elif action_type == "wheel":
                    r["action"] = "wheel"
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

                seg_type = request.form["seg_type"]

                segment = {
                    "name": request.form["seg_name"],
                    "chance": int(request.form["seg_chance"]),
                    "type": seg_type
                }

                if seg_type == "vibration":
                    segment["strength"] = int(request.form["seg_strength"])
                    segment["duration"] = int(request.form["seg_duration"])

                elif seg_type == "action":
                    segment["action"] = request.form["seg_action"]

                elif seg_type == "retry":
                    segment["action"] = ""

                r["segments"].append(segment)

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
