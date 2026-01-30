import json
import os

GOAL_DIR = "data/goals"

def goal_path(profile_key):
    os.makedirs(GOAL_DIR, exist_ok=True)
    return f"{GOAL_DIR}/{profile_key}.json"

def load_goal(profile_key):
    path = goal_path(profile_key)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"title": "", "target": 0, "current": 0}

def save_goal(profile_key, goal):
    path = goal_path(profile_key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(goal, f, ensure_ascii=False, indent=2)
