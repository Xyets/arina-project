import os
from pathlib import Path
from datetime import datetime
from typing import List

LOG_DIR = Path("data/donations")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_path(profile_key: str) -> Path:
    """
    Возвращает путь к файлу логов для профиля.
    """
    return LOG_DIR / f"donations_{profile_key}.log"


def load_logs_from_file(profile_key: str) -> List[str]:
    """
    Загружает логи донатов.
    Возвращает список строк.
    """
    path = log_path(profile_key)

    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f]
    except Exception:
        return []


def add_log(profile_key: str, message: str) -> None:
    """
    Добавляет строку в лог.
    Формат:
        YYYY-MM-DD HH:MM | message
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"{ts} | {message}"

    path = log_path(profile_key)

    # гарантируем, что каталог существует
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as e:
        print(f"⚠️ Ошибка записи лога {path}: {e}")


def clear_logs_file(profile_key: str) -> None:
    """
    Полностью очищает файл логов.
    """
    path = log_path(profile_key)

    try:
        # атомарная очистка
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("")
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp, path)

    except Exception as e:
        print(f"⚠️ Ошибка очистки лога {path}: {e}")
