
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


# -------------------- КОДЫ РЕГИСТРАЦИИ --------------------

def create_registration_code(code):
    """Создаёт новый одноразовый код приглашения."""
    code = code.strip().upper()
    if not code:
        raise ValueError("Код не может быть пустым")

    # На случай, если база была создана старой версией приложения.
    init_db()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO registration_codes (code) VALUES (?)",
            (code,)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("Такой код уже существует")
    finally:
        conn.close()

    return code


def get_registration_code(code):
    """Возвращает код приглашения или None."""
    init_db()
    code = code.strip().upper()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM registration_codes WHERE code = ?",
        (code,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def register_model_with_code(
    code,
    username,
    password_hash,
    display_name,
    lovense_token=None,
    uid=None
):
    """
    Создаёт модель, два её профиля и одновременно использует код.

    Всё выполняется одной транзакцией: если какой-либо этап не удался,
    модель, профили и использование кода не сохраняются частично.
    """
    init_db()

    code = code.strip().upper()
    username = username.strip()

    if not code:
        raise RegistrationError("Введите персональный код")

    if not username:
        raise RegistrationError("Введите имя модели")

    conn = get_connection()

    try:
        # BEGIN IMMEDIATE не позволяет двум одновременным регистрациям
        # использовать один и тот же код.
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM registration_codes WHERE code = ?",
            (code,)
        )
        registration_code = cur.fetchone()

        if not registration_code:
            raise RegistrationError("Неверный персональный код")

        if registration_code["used"]:
            raise RegistrationError("Этот персональный код уже использован")

        cur.execute(
            "SELECT id FROM models WHERE username = ?",
            (username,)
        )
        if cur.fetchone():
            raise RegistrationError("Имя уже занято")

        # Создаём модель внутри той же транзакции.
        cur.execute("""
            INSERT INTO models (username, password_hash, display_name, lovense_token, uid)
            VALUES (?, ?, ?, ?, ?)
        """, (username, password_hash, display_name, lovense_token, uid))

        model_id = cur.lastrowid

        # Сразу создаём private/public профили.
        private_key = f"{username}_private"
        public_key = f"{username}_public"

        cur.execute("""
            INSERT INTO profiles (model_id, profile_key, mode)
            VALUES (?, ?, 'private')
        """, (model_id, private_key))

        cur.execute("""
            INSERT INTO profiles (model_id, profile_key, mode)
            VALUES (?, ?, 'public')
        """, (model_id, public_key))

        # Используем код. Дополнительная проверка used=0 защищает от повторного использования.
        cur.execute("""
            UPDATE registration_codes
            SET used = 1, used_by = ?, used_at = CURRENT_TIMESTAMP
            WHERE id = ? AND used = 0
        """, (model_id, registration_code["id"]))

        if cur.rowcount != 1:
            raise RegistrationError("Этот персональный код уже использован")

        conn.commit()
        return model_id

    except RegistrationError:
        conn.rollback()
        raise
    except sqlite3.IntegrityError as exc:
        conn.rollback()

        # Не показываем модели внутреннюю ошибку SQLite.
        if "username" in str(exc).lower():
            raise RegistrationError("Имя уже занято")

        raise RegistrationError("Не удалось создать модель. Попробуйте ещё раз.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
