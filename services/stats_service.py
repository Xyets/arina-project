import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

BASE_DIR = Path("data/stats")


def _get_stats_path(profile_key: str) -> Path:
    """
    Возвращает путь к stats-файлу для данного профиля.
    """
    return BASE_DIR / f"stats_{profile_key}.json"


# ---------------- LOAD ----------------

def load_stats(profile_key: str) -> Dict[str, Dict]:
    """
    Загружает статистику по profile_key.
    Если файла нет или он повреждён — возвращает пустую структуру.
    """
    path = _get_stats_path(profile_key)

    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------- SAVE ----------------

def save_stats(profile_key: str, stats: Dict[str, Dict]) -> None:
    """
    Сохраняет статистику по profile_key.
    Запись атомарная: сначала .tmp, затем замена.
    """
    path = _get_stats_path(profile_key)
    tmp = path.with_suffix(".json.tmp")

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)


# ---------------- UPDATE CATEGORY ----------------

def update_stats(profile_key: str, category: str, amount: float = 0.0) -> None:
    """
    Обновляет статистику по категории (vibrations/actions/other).
    amount = количество донатов (обычно 1).
    """
    stats = load_stats(profile_key)
    today = datetime.now().strftime("%Y-%m-%d")

    if today not in stats:
        stats[today] = {
            "vibrations": 0.0,
            "actions": 0.0,
            "other": 0.0,
            "total": 0.0,
            "donations_sum": 0.0,
        }

    stats[today][category] += float(amount)

    stats[today]["total"] = (
        stats[today]["vibrations"]
        + stats[today]["actions"]
        + stats[today]["other"]
    )

    save_stats(profile_key, stats)


# ---------------- UPDATE DONATION SUM ----------------

def update_donations_sum(profile_key: str, amount: float = 0.0) -> None:
    """
    Обновляет сумму донатов за день (в поинтах).
    """
    stats = load_stats(profile_key)
    today = datetime.now().strftime("%Y-%m-%d")

    if today not in stats:
        stats[today] = {
            "vibrations": 0.0,
            "actions": 0.0,
            "other": 0.0,
            "total": 0.0,
            "donations_sum": 0.0,
        }

    stats[today]["donations_sum"] += float(amount)

    save_stats(profile_key, stats)


# ---------------- CALCULATE ----------------

def calculate_stats(
    stats: Dict[str, Dict],
    user: str,
    irina_stats: Dict[str, Dict] = None
) -> Tuple[Dict[str, Dict], Dict[str, float]]:
    """
    Считает:
    - вибрации
    - действия
    - иное
    - всего поинтов
    - archi_fee (только Irina)
    - чистый доход (total * 0.7 - archi_fee)
    """

    results = {}

    sum_vibr = sum(d["vibrations"] for d in stats.values())
    sum_act = sum(d["actions"] for d in stats.values())
    sum_other = sum(d["other"] for d in stats.values())
    sum_total = sum(d["total"] for d in stats.values())
    sum_donations = sum(d.get("donations_sum", 0.0) for d in stats.values())

    sum_archi = 0.0
    sum_net = 0.0

    for day, data in stats.items():
        vibr = float(data["vibrations"])
        act = float(data["actions"])
        other = float(data["other"])
        total = float(data["total"])

        # ARCHI (только Irina)
        if user.lower() == "irina":
            archi_fee = vibr * 0.7 * 0.1
        else:
            archi_fee = 0.0

        # NET INCOME
        net_income = total * 0.7 - archi_fee

        results[day] = {
            **data,
            "archi_fee": archi_fee,
            "net_income": net_income
        }

        sum_archi += archi_fee
        sum_net += net_income

    summary = {
        "sum_vibr": sum_vibr,
        "sum_act": sum_act,
        "sum_other": sum_other,
        "sum_total": sum_total,
        "sum_donations": sum_donations,
        "archi_fee": sum_archi,
        "total_income": sum_net,
    }

    return results, summary
