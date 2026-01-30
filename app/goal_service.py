import json
import os

GOAL_DIR = "data/goals"

def goal_path(profile_key):
    os.makedirs(GOAL_DIR, exist_ok=True)
    return f"{GOAL_DIR}/{profile_key}.json"

def load_goal(profile_key):
    path = f"data/goals/{profile_key}.json"
    if not os.path.exists(path):
        return {"title": "", "target": 0, "current": 0}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_goal(profile_key, goal):
    path = goal_path(profile_key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(goal, f, ensure_ascii=False, indent=2)
