import json
import os
from pathlib import Path

GOAL_DIR = Path("data/goals")


def goal_path(profile_key: str) -> Path:
    """
    Возвращает путь к файлу цели для профиля.
    Гарантирует, что каталог существует.
    """
    GOAL_DIR.mkdir(parents=True, exist_ok=True)
    return GOAL_DIR / f"{profile_key}.json"


def load_goal(profile_key: str) -> dict:
    """
    Загружает цель профиля.
    Если файла нет — возвращает пустую структуру.
    """
    path = goal_path(profile_key)

    if not path.exists():
        return {"title": "", "target": 0, "current": 0}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # если файл повреждён — не ломаем панель
        return {"title": "", "target": 0, "current": 0}


def save_goal(profile_key: str, goal: dict) -> None:
    """
    Сохраняет цель профиля.
    Запись атомарная: сначала .tmp, затем замена.
    """
    path = goal_path(profile_key)
    tmp = path.with_suffix(".json.tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(goal, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)
