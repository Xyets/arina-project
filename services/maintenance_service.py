# services/maintenance_service.py

import time
from pathlib import Path


LAST_CLEAN_FILE = Path("data/last_backup_cleanup.txt")


def cleanup_all_backups(base_dir=".", keep=2):
    """
    Удаляет старые .bak файлы во всём проекте.
    Оставляет только N последних для каждого оригинального файла.
    """
    base = Path(base_dir)
    all_bak = list(base.rglob("*.bak"))

    groups = {}

    for bak in all_bak:
        # корректно определяем оригинальный файл
        original = bak.with_suffix("")  # file.json.bak → file.json
        groups.setdefault(original, []).append(bak)

    for original, files in groups.items():
        # сортируем по времени изменения
        files_sorted = sorted(files, key=lambda p: p.stat().st_mtime)

        # удаляем все, кроме последних N
        for old in files_sorted[:-keep]:
            try:
                old.unlink()
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
                    last_clean_ts = float(LAST_CLEAN_FILE.read_text().strip())
                except Exception:
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
                LAST_CLEAN_FILE.write_text(str(now))

        except Exception as e:
            print(f"⚠ Ошибка периодической очистки .bak: {e}")

        # проверяем раз в час
        time.sleep(3600)
