# services/donation_service.py

import json
import redis

from config import CONFIG
from services.vibration_manager import enqueue_vibration
from services.stats_service import update_stats, update_donations_sum
from services.audit import audit_event
from services.reactions_service import apply_reaction_rule
from services.vip_service import update_vip
from services.logs_service import add_log
from services.rules_service import load_rules
from services.goal_service import load_goal, save_goal
from app.goal_app import goal_add_points

redis_client = redis.StrictRedis(host="127.0.0.1", port=6379, db=0)


# ---------------- RULES ----------------

def apply_rule(profile_key, amount, text):
    """
    Применяет правило вибрации/действия.
    """

    rules_file = CONFIG["profiles"][profile_key]["rules_file"]
    rules = load_rules(rules_file)

    for rule in rules.get("rules", []):
        if rule["min"] <= amount <= rule["max"]:

            action = rule.get("action")
            strength = rule.get("strength", 1)
            duration = rule.get("duration", 5)

            mode = profile_key.split("_")[1]

            audit_event(
                profile_key,
                mode,
                {
                    "type": "rule",
                    "matched": "action" if action else "vibration",
                    "amount": amount,
                    "strength": strength,
                    "duration": duration,
                    "text": text,
                },
            )

            # ACTION
            if action and action.strip():
                return {"kind": "action", "action_text": action.strip()}

            # VIBRATION → только очередь
            enqueue_vibration(profile_key, strength, duration)

            return {"kind": "vibration", "strength": strength, "duration": duration}

    return None


# ---------------- DONATION HANDLER ----------------

def handle_donation(profile_key, user_id, name, amount, text): 
    mode = profile_key.split("_")[1]

    # 1. Применяем правила
    rule_result = apply_rule(profile_key, amount, text)

    # 2. Логируем красиво
    if rule_result and rule_result["kind"] == "action":
        add_log(profile_key, f"💸 | {name} → {amount} 🎬 Действие: {rule_result['action_text']}")
    elif rule_result and rule_result["kind"] == "vibration":
        add_log(profile_key, f"💸 | {name} → {amount} 🏰 Вибрация: сила={rule_result['strength']}, время={rule_result['duration']}")
    else:
        add_log(profile_key, f"💸 | {name} → {amount} 🍀 Без действия")

    # 3. Аудит
    audit_event(
        profile_key,
        mode,
        {
            "type": "donation",
            "amount": amount,
            "sender": name,
            "text": text,
        },
    )


    from app.ws_app import ws_send

    ws_send({
        "vip_update": True,
        "user_id": user_id
    }, role="panel")

    # 5. Goal
    goal_add_points(profile_key.split("_")[0], amount)

    user = profile_key.split("_")[0]
    goal_file = CONFIG["profiles"][f"{user}_public"]["goal_file"]
    goal = load_goal(goal_file)
    # 5.5. Отправляем обновление цели в OBS
# 5.5. Отправляем обновление цели в OBS
    ws_send({
        "goal_update": True,
        "goal": {
            "current": goal.get("current", 0),
            "target": goal.get("target", 1),
            "title": goal.get("title", "")
        },
        "profile": profile_key
    }, role="obs", profile_key=profile_key)




    # 6. Статистика
    stats_file = CONFIG["profiles"][profile_key]["stats_file"]

    if rule_result and rule_result["kind"] == "action":
        update_stats(stats_file, "actions", amount)
    elif rule_result and rule_result["kind"] == "vibration":
        update_stats(stats_file, "vibrations", amount)
    else:
        update_stats(stats_file, "other", amount)

    # 7. Реакции OBS
    reactions_file = CONFIG["profiles"][profile_key]["reactions_file"]
    reaction_event = apply_reaction_rule(reactions_file, amount)

    if reaction_event:
        payload = {
            "reaction": {
                "image": reaction_event.get("image"),
                "duration": reaction_event.get("duration", 5)
            },
            "profile": profile_key
        }
        redis_client.publish("obs_reactions", json.dumps(payload))



    return {"goal": goal, "rule": rule_result}
