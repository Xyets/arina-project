import json
import os
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path("data/rules")


def _get_rules_path(profile_key: str) -> Path:
    """
    Возвращает путь к rules-файлу для данного профиля.
    """
    return BASE_DIR / f"rules_{profile_key}.json"


# ---------------- LOAD ----------------

def load_rules(profile_key: str) -> Dict[str, Any]:
    path = _get_rules_path(profile_key)

    if not path.exists():
        return {"rules": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

            # 🔥 СОРТИРОВКА ПРАВИЛ ПО MIN
            data["rules"] = sorted(
                data.get("rules", []),
                key=lambda r: r.get("min", 0)
            )

            return data

    except (json.JSONDecodeError, OSError):
        return {"rules": []}


# ---------------- SAVE ----------------

def save_rules(profile_key: str, rules: Dict[str, Any]) -> None:
    """
    Сохраняет правила вибраций/действий по profile_key.
    Запись атомарная: сначала .tmp, затем замена.
    """
    path = _get_rules_path(profile_key)
    tmp = path.with_suffix(".json.tmp")

    # гарантируем, что каталог существует
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)
