# audit.py
import os
import json
import datetime
import uuid
from pathlib import Path
import threading

AUDIT_ROOT = Path("logs/audit")
LOCK = threading.Lock()

def audit_event(profile_key: str, scope: str, event: dict):
    """
    Записывает событие в JSONL (одна строка = одно событие).
    Каталоги: logs/audit/{profile_key}/{scope}/{YYYY-MM-DD}/events.jsonl
    """
    ts_utc = datetime.datetime.utcnow().isoformat() + "Z"
    day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    folder = AUDIT_ROOT / profile_key / scope / day
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / "events.jsonl"

    record = {
        "ts_utc": ts_utc,
        "ts_local": datetime.datetime.now().isoformat(),
        "profile_key": profile_key,
        "scope": scope,
        # всегда есть уникальный идентификатор события
        "event_id": event.get("donation_id") or event.get("id") or str(uuid.uuid4()),
        "type": event.get("type") or ("donation" if "amount" in event else "vibration"),
        "raw": event,
    }

    line = json.dumps(record, ensure_ascii=False)
    with LOCK:
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"⚠️ Ошибка записи аудита {file_path}: {e}")
