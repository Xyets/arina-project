import os
import json
import uuid
import datetime
import threading
from pathlib import Path
from typing import Dict, Any

AUDIT_ROOT = Path("logs/audit")
LOCK = threading.Lock()


def audit_event(profile_key: str, scope: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Записывает событие в JSONL (одна строка = одно событие).
    Структура каталогов:
        logs/audit/{profile_key}/{scope}/{YYYY-MM-DD}/events.jsonl

    Возвращает записанный объект (включая event_id).
    """

    # защита от пустых ключей
    if not profile_key:
        raise ValueError("profile_key не может быть пустым")

    if not isinstance(event, dict):
        raise ValueError("event должен быть словарём")

    # гарантируем, что корневая папка существует
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)

    # timestamps
    now_local = datetime.datetime.now().replace(microsecond=0)
    now_utc = datetime.datetime.utcnow().replace(microsecond=0)

    day = now_utc.strftime("%Y-%m-%d")
    folder = AUDIT_ROOT / profile_key / scope / day

    # определяем тип события
    event_type = event.get("type")
    if not event_type:
        if "donation_id" in event or "amount" in event:
            event_type = "donation"
        else:
            event_type = "system"

    # формируем запись
    record = {
        "ts_utc": now_utc.isoformat() + "Z",
        "ts_local": now_local.isoformat(),
        "profile_key": profile_key,
        "scope": scope,
        "event_id": str(uuid.uuid4()),
        "type": event_type,
        "raw": event,
    }

    line = json.dumps(record, ensure_ascii=False)

    # потокобезопасная запись
    with LOCK:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            file_path = folder / "events.jsonl"

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())

        except Exception as e:
            print(f"⚠️ Ошибка записи аудита {file_path}: {e}")

    return record
