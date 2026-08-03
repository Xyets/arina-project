import json
import os
from pathlib import Path
from typing import Dict, Any


BASE_DIR = Path("data/goals")


def _get_goal_path(profile_key: str) -> Path:
    """
    Возвращает путь к goal-файлу для данного профиля.
    """
    return BASE_DIR / f"goal_{profile_key}.json"


def load_goal(profile_key: str) -> Dict[str, Any]:
    """
    Загружает цель по profile_key.
    Если файла нет — создаёт пустую структуру.
    """
    path = _get_goal_path(profile_key)

    if not path.exists():
        return {"title": "", "target": 0, "current": 0}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"title": "", "target": 0, "current": 0}


def save_goal(profile_key: str, goal: Dict[str, Any]) -> None:
    """
    Сохраняет цель по profile_key.
    Запись атомарная: сначала .tmp, затем замена.
    """
    path = _get_goal_path(profile_key)
    tmp = path.with_suffix(".json.tmp")

    # гарантируем, что каталог существует
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(goal, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)
