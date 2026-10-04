import sqlite3
import os

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

    # Таблица профилей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id INTEGER NOT NULL,
        profile_key TEXT UNIQUE NOT NULL,
        mode TEXT NOT NULL CHECK (mode IN ('private', 'public')),
        FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
    );
    """)

    # Персональные коды для регистрации моделей.
    # Существующие таблицы models и profiles не изменяются.
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


def create_model(username, password_hash, display_name, lovense_token, uid):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO models (username, password_hash, display_name, lovense_token, uid)
        VALUES (?, ?, ?, ?, ?)
    """, (username, password_hash, display_name, lovense_token, uid))

    conn.commit()
    model_id = cur.lastrowid
    conn.close()
    return model_id


def get_model_by_username(username):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM models WHERE username = ?", (username,))
    row = cur.fetchone()

    conn.close()
    return row


def create_profiles_for_model(model_id, username):
    private_key = f"{username}_private"
    public_key = f"{username}_public"

    conn = get_connection()
    cur = conn.cursor()

    for mode, key in [("private", private_key), ("public", public_key)]:
        cur.execute("""
            INSERT INTO profiles (model_id, profile_key, mode)
            VALUES (?, ?, ?)
        """, (model_id, key, mode))

    conn.commit()
    conn.close()


def get_model_by_id(model_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM models WHERE id = ?", (model_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_profile_by_key(profile_key):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM profiles WHERE profile_key = ?", (profile_key,))
    row = cur.fetchone()
    conn.close()
    return row


def get_model_by_uid(uid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM models WHERE uid = ?", (uid,))
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
        SELECT * FROM registration_codes
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
    Регистрирует новую модель только по действующему персональному коду.
    Код можно использовать только один раз.
    Модель и оба профиля создаются в одной транзакции.
    """
    username = (username or "").strip()
    registration_code = (registration_code or "").strip().upper()

    if not username:
        raise RegistrationError("Введите логин")

    if not registration_code:
        raise RegistrationError("Введите персональный код")

    init_db()

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Не даём двум одновременным регистрациям использовать один код.
        cur.execute("BEGIN IMMEDIATE")

        cur.execute("""
            SELECT id, used
            FROM registration_codes
            WHERE code = ?
        """, (registration_code,))

        code_row = cur.fetchone()

        if code_row is None:
            raise RegistrationError("Неверный персональный код")

        if code_row["used"]:
            raise RegistrationError("Этот персональный код уже использован")

        # Проверяем, что логин ещё свободен.
        cur.execute("""
            SELECT id
            FROM models
            WHERE username = ?
        """, (username,))

        if cur.fetchone() is not None:
            raise RegistrationError("Такой логин уже существует")

        # Создаём модель в существующей таблице models.
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

        # Создаём стандартные private/public профили.
        cur.execute("""
            INSERT INTO profiles (model_id, profile_key, mode)
            VALUES (?, ?, ?)
        """, (model_id, f"{username}_private", "private"))

        cur.execute("""
            INSERT INTO profiles (model_id, profile_key, mode)
            VALUES (?, ?, ?)
        """, (model_id, f"{username}_public", "public"))

        # Помечаем код использованным.
        cur.execute("""
            UPDATE registration_codes
            SET
                used = 1,
                used_by = ?,
                used_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND used = 0
        """, (model_id, code_row["id"]))

        if cur.rowcount != 1:
            raise RegistrationError("Этот персональный код уже использован")

        conn.commit()
        return model_id

    except RegistrationError:
        conn.rollback()
        raise

    except sqlite3.IntegrityError as exc:
        conn.rollback()

        if "username" in str(exc).lower():
            raise RegistrationError("Такой логин уже существует")

        raise RegistrationError(
            "Не удалось создать аккаунт. Проверьте введённые данные"
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
