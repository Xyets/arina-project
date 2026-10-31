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


# Отдельный журнал ошибок приложения. Не смешивается с журналом донатов.
ERROR_LOG_PATH = Path("data/admin_errors.log")
_ERROR_LOG_LIMIT = 2000

def add_error_log(level: str, message: str) -> None:
    """Сохраняет сообщение приложения в отдельный журнал диагностики."""
    try:
        ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_level = str(level or "ERROR").upper()[:12]
        # Each event is one line so the admin page can safely read the tail.
        entry = f"{ts} | {safe_level} | {str(message).replace(chr(10), ' | ').replace(chr(13), ' ')}\n"
        with ERROR_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        # Keep the file bounded; this is diagnostic logging, not an archive.
        try:
            lines = ERROR_LOG_PATH.read_text(encoding="utf-8").splitlines()
            if len(lines) > _ERROR_LOG_LIMIT:
                tmp = ERROR_LOG_PATH.with_suffix(".tmp")
                tmp.write_text("\n".join(lines[-_ERROR_LOG_LIMIT:]) + "\n", encoding="utf-8")
                os.replace(tmp, ERROR_LOG_PATH)
        except OSError:
            pass
    except Exception as exc:
        print(f"FlowTip error-log write failed: {exc}")

def load_error_logs(limit: int = 100):
    """Возвращает последние строки журнала ошибок (новые сверху)."""
    try:
        if not ERROR_LOG_PATH.exists():
            return []
        lines = ERROR_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        return list(reversed(lines[-max(1, min(int(limit), 300)):]))
    except OSError:
        return []
