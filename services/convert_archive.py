import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("❌ Укажите путь к файлу: python convert.py stats.json")
        return

    path = Path(sys.argv[1])

    if not path.exists():
        print(f"❌ Файл не найден: {path}")
        return

    # --- Загружаем старый формат ---
    try:
        with open(path, "r", encoding="utf-8") as f:
            old = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения JSON: {e}")
        return

    if not isinstance(old, dict) or not old:
        print("❌ Некорректный формат: ожидается словарь с днями")
        return

    days = sorted(old.keys())

    # --- Функция суммирования ---
    def get(field):
        return sum(float(old[d].get(field, 0)) for d in days)

    # --- Новый формат ---
    new = {
        "periods": [
            {
                "id": 1,
                "start": days[0],
                "end": days[-1],
                "total_income": get("total"),
                "vibrations": get("vibrations"),
                "actions": get("actions"),
                "other": get("other"),
                "archi_fee": get("archi_fee"),
                "days": old
            }
        ]
    }

    # --- Сохраняем ---
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Ошибка записи файла: {e}")
        return

    print("✔ Готово! Архив конвертирован:", path)


if __name__ == "__main__":
    main()
