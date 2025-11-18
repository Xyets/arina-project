# stats_service.py
import sqlite3
from typing import Dict, Tuple

DB_PATH = "stats.db"

def init_db():
    """Создаёт таблицу статистики, если её ещё нет."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT NOT NULL,
        vibrations INTEGER DEFAULT 0,
        actions INTEGER DEFAULT 0,
        other INTEGER DEFAULT 0,
        total INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

def add_stat(day: str, vibrations: int, actions: int, other: int, total: int):
    """Добавляет запись статистики за день."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO stats (day, vibrations, actions, other, total) VALUES (?, ?, ?, ?, ?)",
        (day, vibrations, actions, other, total)
    )
    conn.commit()
    conn.close()

def get_stats(from_date: str = None, to_date: str = None) -> Dict[str, Dict]:
    """Возвращает словарь статистики по датам."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = "SELECT day, vibrations, actions, other, total FROM stats"
    params = []
    if from_date and to_date:
        query += " WHERE day BETWEEN ? AND ?"
        params = [from_date, to_date]
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    stats = {day: {"vibrations": v, "actions": a, "other": o, "total": t}
             for day, v, a, o, t in rows}
    return stats

def calculate_stats(stats: Dict[str, Dict], user: str) -> Tuple[Dict[str, Dict], Dict[str, int]]:
    """
    Считает net_income и archi_fee для каждого дня и итоговые суммы.
    Возвращает (results, summary).
    """
    results = {}
    sum_vibr = sum(data['vibrations'] for data in stats.values())
    sum_act = sum(data['actions'] for data in stats.values())
    sum_other = sum(data['other'] for data in stats.values())
    sum_total = sum(data['total'] for data in stats.values())

    archi_fee = 0
    total_income = 0

    for day, data in stats.items():
        base_income = data['total'] * 0.7
        if user == "Irina":
            archi = data['vibrations'] * 0.7 * 0.1
            net_income = base_income - archi
            results[day] = {
                **data,
                "archi_fee": archi,
                "net_income": net_income
            }
            archi_fee += archi
            total_income += net_income
        else:
            results[day] = {
                **data,
                "net_income": base_income
            }
            total_income += base_income

    summary = {
        "sum_vibr": sum_vibr,
        "sum_act": sum_act,
        "sum_other": sum_other,
        "sum_total": sum_total,
        "archi_fee": archi_fee,
        "total_income": total_income
    }

    return results, summary
