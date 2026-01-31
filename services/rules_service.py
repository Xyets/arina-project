# services/rules_service.py

import json
import os
from pathlib import Path
from typing import Dict, Any


# ---------------- LOAD ----------------

def load_rules(path: str) -> Dict[str, Any]:
    """
    Загружает правила вибраций/действий из файла по ПОЛНОМУ пути.
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

def save_rules(path: str, rules: Dict[str, Any]) -> None:
    """
    Сохраняет правила вибраций/действий в файл по ПОЛНОМУ пути.
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
