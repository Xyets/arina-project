# services/maintenance_service.py

import os
import glob
import time
from pathlib import Path


LAST_CLEAN_FILE = Path("data/last_backup_cleanup.txt")


def cleanup_all_backups(base_dir=".", keep=2):
    """
    Удаляет старые .bak файлы во всём проекте.
    Оставляет только N последних для каждого оригинального файла.
    """
    all_bak = glob.glob(os.path.join(base_dir, "**", "*.bak"), recursive=True)

    groups = {}
    for bak in all_bak:
        original = bak.split(".")[0]
        groups.setdefault(original, []).append(bak)

    for original, files in groups.items():
        files_sorted = sorted(files, key=os.path.getmtime)
        for old in files_sorted[:-keep]:
            try:
                os.remove(old)
                print(f"🗑 Удалён старый backup: {old}")
            except Exception as e:
                print(f"⚠️ Не удалось удалить {old}: {e}")


def periodic_backup_cleanup(days: int = 5):
    """
    Запускает очистку .bak файлов, если прошло N дней с последней очистки.
    Проверяет раз в час.
    """
    interval_seconds = days * 24 * 60 * 60

    while True:
        try:
            # читаем дату последней очистки
            if LAST_CLEAN_FILE.exists():
                try:
                    with open(LAST_CLEAN_FILE, "r") as f:
                        last_clean_ts = float(f.read().strip())
                except:
                    last_clean_ts = 0
            else:
                last_clean_ts = 0

            now = time.time()

            # если прошло больше N дней — запускаем очистку
            if now - last_clean_ts >= interval_seconds:
                print(f"🧹 Очистка .bak файлов (прошло {days} дней)...")
                cleanup_all_backups("data")
                print("✔ Очистка завершена")

                # сохраняем время последней очистки
                LAST_CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(LAST_CLEAN_FILE, "w") as f:
                    f.write(str(now))

        except Exception as e:
            print(f"⚠ Ошибка периодической очистки .bak: {e}")

        # проверяем раз в час
        time.sleep(3600)
