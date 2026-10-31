import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import logging
import threading

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
_ERROR_LOG_LOCK = threading.Lock()


def add_error_log(level: str, message: str, component: str = "application") -> None:
    """Сохраняет диагностическое событие, не позволяя сбою логирования ломать приложение."""
    try:
        ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_level = str(level or "ERROR").upper()[:12]
        safe_component = str(component or "application").replace("\n", " ").replace("\r", " ")[:80]
        safe_message = str(message).replace("\r", " ").replace("\n", " | ")
        entry = f"{ts} | {safe_level} | {safe_component} | {safe_message}\n"

        # Защищаем запись от одновременных событий внутри одного процесса.
        with _ERROR_LOG_LOCK:
            with ERROR_LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(entry)
            try:
                lines = ERROR_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
                if len(lines) > _ERROR_LOG_LIMIT:
                    tmp = ERROR_LOG_PATH.with_suffix(".tmp")
                    tmp.write_text("\n".join(lines[-_ERROR_LOG_LIMIT:]) + "\n", encoding="utf-8")
                    os.replace(tmp, ERROR_LOG_PATH)
            except OSError:
                # Ошибка ротации не должна прерывать основную работу приложения.
                pass
    except Exception as exc:
        # Последний резервный путь; не вызываем logging отсюда, чтобы избежать рекурсии.
        try:
            print(f"FlowTip error-log write failed: {type(exc).__name__}")
        except Exception:
            pass


def load_error_logs(limit: int = 100):
    """Возвращает последние строки журнала ошибок (новые сверху)."""
    try:
        if not ERROR_LOG_PATH.exists():
            return []
        lines = ERROR_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        return list(reversed(lines[-max(1, min(int(limit), 300)):]))
    except OSError:
        return []


class _FlowTipFileLogHandler(logging.Handler):
    """Перенаправляет ERROR+ из стандартного logging в отдельный журнал FlowTip."""
    def emit(self, record):
        try:
            message = self.format(record)
            add_error_log(record.levelname, message, component=record.name)
        except Exception:
            # Не позволяем ошибке диагностического обработчика сорвать запрос/worker.
            pass


_HANDLER_LOCK = threading.Lock()


def install_error_log_handler(logger=None) -> bool:
    """Устанавливает единый обработчик один раз на указанный logger (по умолчанию root)."""
    target = logger or logging.getLogger()
    with _HANDLER_LOCK:
        for handler in target.handlers:
            if getattr(handler, "_flowtip_error_log_handler", False):
                return False
        handler = _FlowTipFileLogHandler(level=logging.ERROR)
        handler._flowtip_error_log_handler = True
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        target.addHandler(handler)
        return True


def log_exception(component: str, message: str, exc: Optional[BaseException] = None) -> None:
    """Явная запись исключения, включая traceback, для мест без настроенного logger."""
    try:
        if exc is None:
            import sys
            exc = sys.exc_info()[1]
        details = f"{message}: {type(exc).__name__}: {exc}" if exc else message
        add_error_log("ERROR", details, component=component)
    except Exception:
        pass
