# services/reactions_service.py

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


# ---------------- LOAD ----------------

def load_reaction_rules(path: str) -> Dict[str, Any]:
    """
    Загружает правила реакций из файла по ПОЛНОМУ пути.
    Если файла нет или он повреждён — возвращает пустую структуру.
    """
    path = Path(path)

    if not path.exists():
        return {"rules": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"rules": []}


# ---------------- SAVE ----------------

def save_reaction_rules(path: str, rules: Dict[str, Any]) -> None:
    """
    Сохраняет правила реакций в файл по ПОЛНОМУ пути.
    Запись атомарная: сначала .tmp, затем замена.
    """
    path = Path(path)
    tmp = path.with_suffix(".json.tmp")

    # гарантируем, что каталог существует
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)


# ---------------- APPLY RULE ----------------

def apply_reaction_rule(path: str, amount: int) -> Optional[Dict[str, Any]]:
    """
    Проверяет сумму доната против правил реакций.
    Если совпадает — возвращает событие для OBS:
        {
            "reaction": rule_id,
            "profile": profile_key,
            "duration": X,
            "image": "reactions/xxx.png"
        }
    """
    rules = load_reaction_rules(path)

    for rule in rules.get("rules", []):
        if rule["min_points"] <= amount <= rule["max_points"]:
            return {
                "reaction": rule["id"],
                "duration": rule.get("duration", 5),
                "image": rule.get("image")
            }

    return None
