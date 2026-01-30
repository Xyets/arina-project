# services/reactions_service.py

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

REACTIONS_DIR = Path("data/reactions")
REACTIONS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------- PATH UTILITY ----------------

def reactions_path(profile_key: str) -> Path:
    """
    Возвращает путь к файлу правил реакций для профиля.
    """
    return REACTIONS_DIR / f"reactions_{profile_key}.json"


# ---------------- LOAD ----------------

def load_reaction_rules(profile_key: str) -> Dict[str, Any]:
    """
    Загружает правила реакций.
    Если файла нет или он повреждён — возвращает пустую структуру.
    """
    path = reactions_path(profile_key)

    if not path.exists():
        return {"rules": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"rules": []}


# ---------------- SAVE ----------------

def save_reaction_rules(profile_key: str, rules: Dict[str, Any]) -> None:
    """
    Сохраняет правила реакций.
    Запись атомарная: сначала .tmp, затем замена.
    """
    path = reactions_path(profile_key)
    tmp = path.with_suffix(".json.tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)


# ---------------- APPLY RULE ----------------

def apply_reaction_rule(profile_key: str, amount: int) -> Optional[Dict[str, Any]]:
    """
    Проверяет сумму доната против правил реакций.
    Если совпадает — возвращает событие для OBS:
        {
            "reaction": rule_id,
            "profile": profile_key,
            "duration": X,
            "image": "reactions/xxx.png"
        }
    Если нет совпадений — возвращает None.
    """
    rules = load_reaction_rules(profile_key)

    for rule in rules.get("rules", []):
        if rule["min_points"] <= amount <= rule["max_points"]:
            return {
                "reaction": rule["id"],
                "profile": profile_key,
                "duration": rule.get("duration", 5),
                "image": rule.get("image")
            }

    return None
