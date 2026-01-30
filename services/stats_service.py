# services/stats_service.py

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

STATS_DIR = Path("data/stats")
STATS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------- PATH ----------------

def stats_path(profile_key: str) -> Path:
    return STATS_DIR / f"stats_{profile_key}.json"


# ---------------- LOAD ----------------

def load_stats(profile_key: str) -> Dict[str, Dict]:
    path = stats_path(profile_key)

    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------- SAVE ----------------

def save_stats(profile_key: str, stats: Dict[str, Dict]) -> None:
    path = stats_path(profile_key)
    tmp = path.with_suffix(".json.tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)


# ---------------- UPDATE CATEGORY ----------------

def update_stats(profile_key: str, category: str, amount: float = 0.0) -> None:
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

def calculate_stats(stats: Dict[str, Dict], user: str, irina_stats: Dict[str, Dict] = None) -> Tuple[Dict[str, Dict], Dict[str, float]]:
    results = {}

    sum_vibr = sum(float(d["vibrations"]) for d in stats.values())
    sum_act = sum(float(d["actions"]) for d in stats.values())
    sum_other = sum(float(d["other"]) for d in stats.values())
    sum_total = sum(float(d["total"]) for d in stats.values())
    sum_donations = sum(float(d.get("donations_sum", 0.0)) for d in stats.values())

    archi_fee = 0.0
    total_income = 0.0

    for day, data in stats.items():
        base_income = float(data["total"]) * 0.7

        if user == "Irina":
            archi = float(data["vibrations"]) * 0.7 * 0.1
            net_income = base_income - archi
            results[day] = {**data, "archi_fee": archi, "net_income": net_income}
            archi_fee += archi
            total_income += net_income
        else:
            net_income = base_income
            results[day] = {**data, "net_income": net_income}
            total_income += net_income

    if user == "Arina" and irina_stats:
        archi_fee = sum(float(d["vibrations"]) * 0.7 * 0.1 for d in irina_stats.values())

    summary = {
        "sum_vibr": sum_vibr,
        "sum_act": sum_act,
        "sum_other": sum_other,
        "sum_total": sum_total,
        "sum_donations": sum_donations,
        "archi_fee": archi_fee,
        "total_income": total_income,
    }

    return results, summary
