import sqlite3
from typing import Dict, Tuple

DB_PATH = "stats.db"

def init_db():
    """Создаёт таблицу статистики, если её ещё нет."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stats (
        day TEXT PRIMARY KEY,
        vibrations REAL DEFAULT 0,
        actions REAL DEFAULT 0,
        other REAL DEFAULT 0,
        total REAL DEFAULT 0,
        donations_sum REAL DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

def add_stat(day: str, vibrations: float, actions: float, other: float, donations_sum: float):
    """
    Добавляет или обновляет запись статистики за день (UPSERT).
    total всегда пересчитывается как сумма категорий.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO stats (day, vibrations, actions, other, total, donations_sum)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(day) DO UPDATE SET
        vibrations = vibrations + excluded.vibrations,
        actions = actions + excluded.actions,
        other = other + excluded.other,
        donations_sum = donations_sum + excluded.donations_sum,
        total = (vibrations + excluded.vibrations) +
                (actions + excluded.actions) +
                (other + excluded.other)
    """, (day, vibrations, actions, other, vibrations+actions+other, donations_sum))
    conn.commit()
    conn.close()

def get_stats(from_date: str = None, to_date: str = None) -> Dict[str, Dict]:
    """Возвращает словарь статистики по датам."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = "SELECT day, vibrations, actions, other, total, donations_sum FROM stats"
    params = []
    if from_date and to_date:
        query += " WHERE day BETWEEN ? AND ?"
        params = [from_date, to_date]
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    stats = {
        day: {
            "vibrations": float(v),
            "actions": float(a),
            "other": float(o),
            "total": float(t),
            "donations_sum": float(ds)
        }
        for day, v, a, o, t, ds in rows
    }
    return stats

def calculate_stats(stats: Dict[str, Dict], user: str, irina_stats: Dict[str, Dict] = None) -> Tuple[Dict[str, Dict], Dict[str, float]]:
    """
    Считает net_income и archi_fee для каждого дня и итоговые суммы.
    Возвращает (results, summary).
    """
    results = {}
    sum_vibr = sum(float(data['vibrations']) for data in stats.values())
    sum_act = sum(float(data['actions']) for data in stats.values())
    sum_other = sum(float(data['other']) for data in stats.values())
    sum_total = sum(float(data['total']) for data in stats.values())
    sum_donations = sum(float(data.get('donations_sum', 0.0)) for data in stats.values())

    archi_fee = 0.0
    total_income = 0.0

    for day, data in stats.items():
        base_income = float(data['total']) * 0.7
        if user == "Irina":
            archi = float(data['vibrations']) * 0.7 * 0.1
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
        "total_income": total_income
    }

    return results, summary
