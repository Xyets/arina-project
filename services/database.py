import sqlite3
import os
import re

DB_PATH = "data/models.db"


def get_connection():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Таблица моделей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        lovense_token TEXT,
        uid TEXT UNIQUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Таблица профилей.
    #
    # В существующей базе profiles уже содержит обязательные поля:
    # rules_file
    # vip_file
    # stats_file
    # goal_file
    # reactions_file
    #
    # Здесь CREATE TABLE используется только для новой базы.
    # Существующая таблица не изменяется.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id INTEGER NOT NULL,
        profile_key TEXT UNIQUE NOT NULL,
        mode TEXT NOT NULL CHECK (mode IN ('private', 'public')),
        rules_file TEXT NOT NULL,
        vip_file TEXT NOT NULL,
        stats_file TEXT NOT NULL,
        goal_file TEXT NOT NULL,
        reactions_file TEXT NOT NULL,
        FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
    );
    """)

    # Персональные коды регистрации моделей.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS registration_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        used INTEGER NOT NULL DEFAULT 0,
        used_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        used_at DATETIME,
        FOREIGN KEY (used_by) REFERENCES models(id) ON DELETE SET NULL
    );
    """)

    conn.commit()
    conn.close()


class RegistrationError(Exception):
    """Ошибка регистрации модели по персональному коду."""


def make_model_uid(username):
    """
    Формирует один UID на модель, общий для private и public:
    Kira -> kira_001.
    """
    base = (username or "").strip().lower()
    base = re.sub(r"[^a-z0-9_-]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_-")

    if not base:
        base = "model"

    return f"{base}_001"


def create_model(username, password_hash, display_name, lovense_token, uid=None):
    username = (username or "").strip()
    uid = (uid or "").strip() or make_model_uid(username)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO models (
            username,
            password_hash,
            display_name,
            lovense_token,
            uid
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        username,
        password_hash,
        display_name,
        lovense_token,
        uid
    ))

    conn.commit()
    model_id = cur.lastrowid
    conn.close()

    return model_id


def get_model_by_username(username):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM models WHERE username = ?",
        (username,)
    )

    row = cur.fetchone()

    conn.close()
    return row


def create_profiles_for_model(model_id, username):
    """
    Создаёт private/public профили для модели
    со всеми обязательными файлами.
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        for mode in ("private", "public"):
            profile_key = f"{username}_{mode}"

            rules_file = f"data/rules/rules_{profile_key}.json"
            vip_file = f"data/vip/vip_{profile_key}.json"
            stats_file = f"data/stats/stats_{profile_key}.json"
            goal_file = f"data/goals/goal_{profile_key}.json"
            reactions_file = f"data/reactions/reactions_{profile_key}.json"

            cur.execute("""
                INSERT INTO profiles (
                    model_id,
                    profile_key,
                    mode,
                    rules_file,
                    vip_file,
                    stats_file,
                    goal_file,
                    reactions_file
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model_id,
                profile_key,
                mode,
                rules_file,
                vip_file,
                stats_file,
                goal_file,
                reactions_file
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_model_by_id(model_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM models WHERE id = ?",
        (model_id,)
    )

    row = cur.fetchone()

    conn.close()
    return row


def get_profile_by_key(profile_key):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM profiles WHERE profile_key = ?",
        (profile_key,)
    )

    row = cur.fetchone()

    conn.close()
    return row


def get_model_by_uid(uid):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM models WHERE uid = ?",
        (uid,)
    )

    row = cur.fetchone()

    conn.close()
    return row


def create_registration_code(code):
    """Создаёт новый персональный код регистрации."""

    code = (code or "").strip().upper()

    if not code:
        raise ValueError("Код не может быть пустым")

    init_db()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO registration_codes (code)
            VALUES (?)
        """, (code,))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("Такой код уже существует")

    finally:
        conn.close()

    return code


def get_registration_code(code):
    """Возвращает персональный код или None, если его нет."""

    code = (code or "").strip().upper()

    if not code:
        return None

    init_db()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM registration_codes
        WHERE code = ?
    """, (code,))

    row = cur.fetchone()

    conn.close()
    return row


def register_model_with_code(
    username,
    password_hash,
    display_name,
    lovense_token,
    uid,
    registration_code
):
    """
    Регистрирует новую модель только по действующему
    персональному коду.

    Код можно использовать только один раз.

    Модель, private/public профили и отметка использования
    регистрационного кода создаются в одной транзакции.
    """

    username = (username or "").strip()
    registration_code = (registration_code or "").strip().upper()
    uid = (uid or "").strip() or make_model_uid(username)

    if not username:
        raise RegistrationError("Введите логин")

    if not password_hash:
        raise RegistrationError("Введите пароль")

    if not display_name:
        display_name = username

    if not registration_code:
        raise RegistrationError("Введите персональный код")

    init_db()

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Блокируем запись на время регистрации,
        # чтобы один код нельзя было использовать одновременно
        # в двух запросах.
        cur.execute("BEGIN IMMEDIATE")

        # Проверяем персональный код.
        cur.execute("""
            SELECT id, used
            FROM registration_codes
            WHERE code = ?
        """, (registration_code,))

        code_row = cur.fetchone()

        if code_row is None:
            raise RegistrationError("Неверный персональный код")

        if code_row["used"]:
            raise RegistrationError(
                "Этот персональный код уже использован"
            )

        # Проверяем, что логин свободен.
        cur.execute("""
            SELECT id
            FROM models
            WHERE username = ?
        """, (username,))

        if cur.fetchone() is not None:
            raise RegistrationError(
                "Такой логин уже существует"
            )

        # Создаём модель.
        cur.execute("""
            INSERT INTO models (
                username,
                password_hash,
                display_name,
                lovense_token,
                uid
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            username,
            password_hash,
            display_name,
            lovense_token,
            uid
        ))

        model_id = cur.lastrowid

        # Создаём private и public профили.
        #
        # Формат полностью соответствует существующим
        # профилям Arina и Irina.
        for mode in ("private", "public"):

            profile_key = f"{username}_{mode}"

            rules_file = (
                f"data/rules/rules_{profile_key}.json"
            )

            vip_file = (
                f"data/vip/vip_{profile_key}.json"
            )

            stats_file = (
                f"data/stats/stats_{profile_key}.json"
            )

            goal_file = (
                f"data/goals/goal_{profile_key}.json"
            )

            reactions_file = (
                f"data/reactions/reactions_{profile_key}.json"
            )

            cur.execute("""
                INSERT INTO profiles (
                    model_id,
                    profile_key,
                    mode,
                    rules_file,
                    vip_file,
                    stats_file,
                    goal_file,
                    reactions_file
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model_id,
                profile_key,
                mode,
                rules_file,
                vip_file,
                stats_file,
                goal_file,
                reactions_file
            ))

        # Помечаем персональный код использованным.
        cur.execute("""
            UPDATE registration_codes
            SET
                used = 1,
                used_by = ?,
                used_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND used = 0
        """, (
            model_id,
            code_row["id"]
        ))

        if cur.rowcount != 1:
            raise RegistrationError(
                "Этот персональный код уже использован"
            )

        # Всё успешно — сохраняем всю регистрацию.
        conn.commit()

        return model_id

    except RegistrationError:
        conn.rollback()
        raise

    except sqlite3.IntegrityError as exc:
        conn.rollback()

        print(
            "REGISTRATION SQLITE ERROR:",
            repr(exc),
            flush=True
        )

        error_text = str(exc).lower()

        if "username" in error_text:
            raise RegistrationError(
                "Такой логин уже существует"
            )

        if "profile_key" in error_text:
            raise RegistrationError(
                "Профиль с таким именем уже существует"
            )

        if "uid" in error_text:
            raise RegistrationError(
                "Такой UID уже существует"
            )

        raise RegistrationError(
            "Не удалось создать аккаунт. Проверьте введённые данные"
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
