import json
import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    old = json.load(f)

days = list(old.keys())
days_sorted = sorted(days)

def get(field):
    return sum(old[d].get(field, 0) for d in days)

new = {
    "periods": [
        {
            "id": 1,
            "start": days_sorted[0],
            "end": days_sorted[-1],
            "total_income": get("total"),
            "vibrations": get("vibrations"),
            "actions": get("actions"),
            "other": get("other"),
            "archi_fee": get("archi_fee"),
            "days": old
        }
    ]
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(new, f, indent=2, ensure_ascii=False)

print("Готово! Архив конвертирован:", path)
