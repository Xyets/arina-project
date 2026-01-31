import json
import os
from pathlib import Path
from typing import Dict, Any


def load_goal(path: str) -> Dict[str, Any]:
    """
    Загружает цель из файла по ПОЛНОМУ пути.
    Если файла нет — возвращает пустую структуру.
    """
    path = Path(path)

    if not path.exists():
        return {"title": "", "target": 0, "current": 0}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"title": "", "target": 0, "current": 0}


def save_goal(path: str, goal: Dict[str, Any]) -> None:
    """
    Сохраняет цель в файл по ПОЛНОМУ пути.
    Запись атомарная: сначала .tmp, затем замена.
    """
    path = Path(path)
    tmp = path.with_suffix(".json.tmp")

    # гарантируем, что каталог существует
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(goal, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)
