# services/vip_service.py

import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from services.audit import audit_event


VIP_DIR = Path("data/vip")
VIP_DIR.mkdir(parents=True, exist_ok=True)


# ---------------- PATH ----------------

def vip_path(profile_key: str) -> Path:
    """
    Возвращает путь к файлу VIP-данных профиля.
    """
    return VIP_DIR / f"vip_{profile_key}.json"


# ---------------- LOAD ----------------

def load_vip_file(profile_key: str) -> Dict[str, Any]:
    """
    Загружает VIP-данные профиля.
    Если файла нет или он повреждён — возвращает пустую структуру.
    """
    path = vip_path(profile_key)

    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------- SAVE ----------------

def save_vip_file(profile_key: str, vip_data: Dict[str, Any]) -> None:
    """
    Сохраняет VIP-данные.
    Запись атомарная: сначала .tmp, затем замена.
    Создаёт резервную копию .bak с датой.
    """
    path = vip_path(profile_key)
    tmp = path.with_suffix(".json.tmp")

    # резервная копия
    if path.exists():
        backup = path.with_suffix(f".{datetime.now().strftime('%Y-%m-%d')}.bak")
        shutil.copy(path, backup)

    # атомарная запись
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(vip_data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)


# ---------------- UPDATE ----------------

def update_vip(
    profile_key: str,
    user_id: str,
    name: Optional[str] = None,
    amount: float = 0.0,
    event: Optional[str] = None
) -> Dict[str, Any]:
    """
    Обновляет VIP-данные:
      - имя
      - сумма донатов
      - события входа/выхода
      - счётчики логинов
    """

    vip_data = load_vip_file(profile_key)

    # если нет записи — создаём
    if user_id not in vip_data:
        vip_data[user_id] = {
            "name": name or "Аноним",
            "alias": "",
            "total": 0.0,
            "notes": "",
            "login_count": 0,
            "last_login": "",
            "_previous_login": "",
            "blocked": False,
            "_just_logged_in": False,
        }

    user = vip_data[user_id]

    # обновляем имя
    if name and (not user["name"] or user["name"] == "Аноним"):
        user["name"] = name

    # обновляем сумму донатов
    if amount > 0:
        user["total"] = float(user.get("total", 0.0)) + float(amount)

        audit_event(
            profile_key,
            profile_key.split("_")[1],
            {"type": "vip_total_increment", "user_id": user_id, "amount": amount}
        )

    # события входа/выхода
    if event:
        event = event.lower()

        if event == "login":
            user["login_count"] += 1
            if user["last_login"]:
                user["_previous_login"] = user["last_login"]

            user["last_login"] = datetime.now().replace(microsecond=0).isoformat(sep=" ")
            user["_just_logged_in"] = True

            audit_event(
                profile_key,
                profile_key.split("_")[1],
                {"type": "vip_login", "user_id": user_id, "name": user["name"]}
            )

        elif event == "logout":
            audit_event(
                profile_key,
                profile_key.split("_")[1],
                {"type": "vip_logout", "user_id": user_id, "name": user["name"]}
            )

    save_vip_file(profile_key, vip_data)
    return user
