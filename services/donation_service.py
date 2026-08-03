import json

from services.redis_client import redis_client
from services.stats_service import update_stats
from services.audit import audit_event
from services.reactions_service import apply_reaction_rule
from services.vip_service import update_vip
from services.logs_service import add_log
from services.rules_service import load_rules
from services.goal_service import load_goal
from app.goal_app import goal_add_points


# ---------------- RULES ----------------

def apply_rule(profile_key, amount, text):
    """
    Применяет правила вибраций/действий/колеса по profile_key.
    """
    rules = load_rules(profile_key)

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

            # WHEEL
            if rule.get("type") == "wheel":
                return {"kind": "wheel", "segments": rule.get("segments", [])}

            # ACTION
            if action and action.strip():
                return {"kind": "action", "action_text": action.strip()}

            # VIBRATION → через Redis → ws_app → очередь
            redis_client.publish("vibrations", json.dumps({
                "profile_key": profile_key,
                "strength": strength,
                "duration": duration
            }))

            return {"kind": "vibration", "strength": strength, "duration": duration}

    return None


# ---------------- DONATION HANDLER ----------------

def handle_donation(profile_key, user_id, name, amount, text):
    mode = profile_key.split("_")[1]

    # 1. Применяем правила
    rule_result = apply_rule(profile_key, amount, text)

    # --- WHEEL ---
    if rule_result and rule_result["kind"] == "wheel":
        segments = rule_result["segments"]

        if segments:
            redis_client.publish("obs_reactions", json.dumps({
                "wheel_spin": True,
                "profile": profile_key,
                "segments": segments
            }))

        return {"goal": None, "rule": rule_result}

    # 2. Логируем
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

    # 4. VIP обновление
    update_vip(profile_key, user_id, name=name, amount=amount)

    # 5. Обновление цели (всегда public)
    user = profile_key.split("_")[0]
    goal_add_points(user, amount)

    public_key = f"{user}_public"
    goal = load_goal(public_key)

    redis_client.publish("obs_reactions", json.dumps({
        "goal_update": True,
        "goal": {
            "current": goal.get("current", 0),
            "target": goal.get("target", 1),
            "title": goal.get("title", "")
        },
        "profile": profile_key
    }))

    # 6. Статистика
    if rule_result and rule_result["kind"] == "action":
        update_stats(profile_key, "actions", amount)
    elif rule_result and rule_result["kind"] == "vibration":
        update_stats(profile_key, "vibrations", amount)
    else:
        update_stats(profile_key, "other", amount)

    # 7. OBS реакции
    reaction_event = apply_reaction_rule(profile_key, amount)

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
