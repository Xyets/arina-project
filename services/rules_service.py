# services/rules_service.py

import json
import os
from pathlib import Path
from typing import Dict, Any

RULES_DIR = Path("data/rules")
RULES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------- PATH UTILITY ----------------

def rules_path(profile_key: str) -> Path:
    """
    Возвращает путь к файлу правил вибраций/действий.
    """
    return RULES_DIR / f"rules_{profile_key}.json"


# ---------------- LOAD ----------------

def load_rules(profile_key: str) -> Dict[str, Any]:
    """
    Загружает правила вибраций/действий.
    Если файла нет или он повреждён — возвращает пустую структуру.
    """
    path = rules_path(profile_key)

    if not path.exists():
        return {"rules": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"rules": []}


# ---------------- SAVE ----------------

def save_rules(profile_key: str, rules: Dict[str, Any]) -> None:
    """
    Сохраняет правила вибраций/действий.
    Запись атомарная: сначала .tmp, затем замена.
    """
    path = rules_path(profile_key)
    tmp = path.with_suffix(".json.tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)
