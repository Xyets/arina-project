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

    # Таблица профилей (упрощённая)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id INTEGER NOT NULL,
        profile_key TEXT UNIQUE NOT NULL,
        mode TEXT NOT NULL CHECK (mode IN ('private', 'public')),
        FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


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
