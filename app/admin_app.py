"""Owner-only FlowTip Admin starter.

Credentials are supplied through environment variables:
  FLOWTIP_ADMIN_USERNAME
  FLOWTIP_ADMIN_PASSWORD_HASH

Generate the password hash with:
  python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Admin password: ')))"
"""
from functools import wraps
import hmac
import os
import secrets
import threading
import json
from datetime import datetime, date, timedelta
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from services.database import get_connection, create_registration_code as db_create_registration_code

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Per-process defense-in-depth throttling. In a multi-worker deployment, also
# configure request rate limiting at Nginx/the reverse proxy.
_ATTEMPTS = {}
_ATTEMPTS_LOCK = threading.Lock()
_MAX_ATTEMPTS = 5
_LOCK_SECONDS = 15 * 60


def _credentials():
    username = os.environ.get("FLOWTIP_ADMIN_USERNAME", "").strip()
    password_hash = os.environ.get("FLOWTIP_ADMIN_PASSWORD_HASH", "").strip()
    if not username or not password_hash:
        current_app.logger.error(
            "FlowTip Admin is disabled: FLOWTIP_ADMIN_USERNAME and/or "
            "FLOWTIP_ADMIN_PASSWORD_HASH is not configured."
        )
        return None, None
    return username, password_hash


def _csrf_token():
    token = session.get("admin_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin_csrf_token"] = token
    return token


def _valid_csrf():
    supplied = request.form.get("csrf_token", "")
    expected = session.get("admin_csrf_token", "")
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


def _client_key():
    # Do not trust X-Forwarded-For here; only use it if ProxyFix is deliberately
    # configured for the known reverse proxy elsewhere in the application.
    return request.remote_addr or "unknown"


def _is_rate_limited(key):
    now = time.monotonic()
    with _ATTEMPTS_LOCK:
        entry = _ATTEMPTS.get(key)
        if not entry:
            return False
        failures, locked_until = entry
        if locked_until > now:
            return True
        if locked_until:
            _ATTEMPTS.pop(key, None)
    return False


def _record_failure(key):
    now = time.monotonic()
    with _ATTEMPTS_LOCK:
        failures, locked_until = _ATTEMPTS.get(key, (0, 0))
        if locked_until > now:
            return
        failures += 1
        _ATTEMPTS[key] = (failures, now + _LOCK_SECONDS if failures >= _MAX_ATTEMPTS else 0)


def _clear_failures(key):
    with _ATTEMPTS_LOCK:
        _ATTEMPTS.pop(key, None)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        configured_username, _ = _credentials()
        authenticated_as = session.get("flowtip_admin_username")
        if (
            session.get("flowtip_admin_authenticated") is not True
            or not configured_username
            or not isinstance(authenticated_as, str)
            or not hmac.compare_digest(authenticated_as, configured_username)
        ):
            session.pop("flowtip_admin_authenticated", None)
            session.pop("flowtip_admin_username", None)
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    configured_username, password_hash = _credentials()
    if not configured_username or not password_hash:
        return render_template("admin_login.html", disabled=True, csrf_token=_csrf_token()), 503

    if session.get("flowtip_admin_authenticated") is True:
        return redirect(url_for("admin.dashboard"))

    client_key = _client_key()
    if _is_rate_limited(client_key):
        return render_template(
            "admin_login.html", error="Слишком много неудачных попыток. Попробуйте позже.",
            csrf_token=_csrf_token(),
        ), 429

    error = None
    if request.method == "POST":
        if not _valid_csrf():
            abort(400, description="Недействительный CSRF-токен")

        submitted_username = request.form.get("username", "").strip()
        submitted_password = request.form.get("password", "")
        username_ok = hmac.compare_digest(submitted_username, configured_username)
        try:
            password_ok = check_password_hash(password_hash, submitted_password)
        except (ValueError, TypeError):
            current_app.logger.exception("Invalid FLOWTIP_ADMIN_PASSWORD_HASH format")
            password_ok = False

        if username_ok and password_ok:
            _clear_failures(client_key)
            # Clear any model session first: admin and model auth must not mix.
            session.clear()
            session["flowtip_admin_authenticated"] = True
            session["flowtip_admin_username"] = configured_username
            session["admin_csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(url_for("admin.dashboard"))

        _record_failure(client_key)
        error = "Неверный логин или пароль"

    return render_template("admin_login.html", error=error, csrf_token=_csrf_token())


@admin_bp.route("/logout", methods=["POST"])
@admin_required
def logout():
    if not _valid_csrf():
        abort(400, description="Недействительный CSRF-токен")
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.route("/registration-codes/create", methods=["POST"])
@admin_required
def create_registration_code_route():
    """Create one high-entropy registration code without exposing model credentials."""
    if not _valid_csrf():
        abort(400, description="Недействительный CSRF-токен")

    # The DB helper normalizes codes to uppercase. Hex keeps the code easy to copy
    # and avoids ambiguous characters such as O/0 and I/1.
    for _ in range(5):
        code = secrets.token_hex(5).upper()
        try:
            db_create_registration_code(code)
            flash(f"Создан регистрационный ключ: {code}", "success")
            break
        except ValueError:
            # Extremely unlikely collision; retry with a new random value.
            continue
    else:
        current_app.logger.exception("Could not create a registration code after retries")
        flash("Не удалось создать ключ. Проверь журнал приложения.", "error")

    return redirect(url_for("admin.dashboard") + "#registration-codes")


@admin_bp.route("/registration-codes/<int:code_id>/delete", methods=["POST"])
@admin_required
def delete_registration_code_route(code_id):
    """Delete only an unused registration code; preserve used-code history."""
    if not _valid_csrf():
        abort(400, description="Недействительный CSRF-токен")

    conn = get_connection()
    try:
        # Do not delete a key if it was consumed after the page was rendered.
        cursor = conn.execute(
            "DELETE FROM registration_codes WHERE id = ? AND used = 0",
            (code_id,),
        )
        conn.commit()
        if cursor.rowcount == 1:
            flash("Неиспользованный регистрационный ключ удалён.", "success")
        else:
            flash(
                "Ключ не удалён: он уже использован или не существует. "
                "Использованные ключи сохраняются в истории.",
                "error",
            )
    except Exception:
        conn.rollback()
        current_app.logger.exception("Could not delete registration code id=%s", code_id)
        flash("Не удалось удалить ключ. Проверь журнал приложения.", "error")
    finally:
        conn.close()

    return redirect(url_for("admin.dashboard") + "#registration-codes")


@admin_bp.route("/")
@admin_required
def dashboard():
    conn = get_connection()
    try:
        model_count = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        profile_count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        try:
            unused_codes = conn.execute(
                "SELECT COUNT(*) FROM registration_codes WHERE used = 0"
            ).fetchone()[0]
        except Exception:
            # Allows the dashboard to open if an older DB lacks this optional table.
            unused_codes = None

        models = conn.execute("""
            SELECT m.id, m.username, m.display_name, m.created_at, m.uid,
                   COUNT(p.id) AS profile_count
            FROM models AS m
            LEFT JOIN profiles AS p ON p.model_id = m.id
            GROUP BY m.id, m.username, m.display_name, m.created_at, m.uid
            ORDER BY m.created_at DESC, m.id DESC
        """).fetchall()
        codes = conn.execute("""
            SELECT rc.id, rc.code, rc.used, rc.created_at, rc.used_at,
                   m.username AS used_by_username
            FROM registration_codes AS rc
            LEFT JOIN models AS m ON m.id = rc.used_by
            ORDER BY rc.created_at DESC, rc.id DESC
        """).fetchall()
    except Exception:
        current_app.logger.exception("Could not load FlowTip Admin overview")
        abort(500)
    finally:
        conn.close()

    conn = get_connection()
    try:
        profiles = conn.execute("""
            SELECT p.profile_key, p.mode, m.username
            FROM profiles AS p
            JOIN models AS m ON m.id = p.model_id
            ORDER BY m.username COLLATE NOCASE, p.mode
        """).fetchall()
    finally:
        conn.close()

    selected_profile = (request.args.get("profile") or "").strip()
    allowed_profiles = {row["profile_key"] for row in profiles}
    if selected_profile not in allowed_profiles:
        selected_profile = profiles[0]["profile_key"] if profiles else ""

    today = date.today().isoformat()
    date_from = (request.args.get("date_from") or today).strip()
    date_to = (request.args.get("date_to") or today).strip()
    sender_query = (request.args.get("sender") or "").strip()[:100]
    amount_query = (request.args.get("amount") or "").strip()[:30]
    try:
        from_day = date.fromisoformat(date_from)
        to_day = date.fromisoformat(date_to)
        if from_day > to_day:
            raise ValueError("date_from after date_to")
    except ValueError:
        date_from = date_to = today
        from_day = to_day = date.today()

    try:
        amount_min = float(amount_query) if amount_query else None
        if amount_min is not None and amount_min < 0:
            raise ValueError("negative amount")
    except ValueError:
        amount_min = None
        amount_query = ""

    donations = []
    if selected_profile:
        profile_row = next((p for p in profiles if p["profile_key"] == selected_profile), None)
        if profile_row:
            audit_root = Path("logs/audit") / selected_profile / str(profile_row["mode"])
            day = from_day
            while day <= to_day:
                event_file = audit_root / day.isoformat() / "events.jsonl"
                try:
                    with event_file.open("r", encoding="utf-8") as handle:
                        for line in handle:
                            try:
                                record = json.loads(line)
                                raw = record.get("raw") or {}
                                if record.get("type") != "donation" and raw.get("type") != "donation":
                                    continue
                                sender = str(raw.get("sender") or raw.get("name") or "Аноним")
                                amount = float(raw.get("amount") or 0)
                                if sender_query and sender_query.casefold() not in sender.casefold():
                                    continue
                                if amount_min is not None and amount < amount_min:
                                    continue
                                donations.append({
                                    "timestamp": record.get("ts_local") or record.get("ts_utc") or "—",
                                    "sender": sender,
                                    "amount": amount,
                                    "text": str(raw.get("text") or ""),
                                    "event_id": str(record.get("event_id") or ""),
                                })
                            except (ValueError, TypeError, json.JSONDecodeError):
                                continue
                except FileNotFoundError:
                    pass
                except OSError:
                    current_app.logger.exception("Could not read donation audit file %s", event_file)
                day += timedelta(days=1)

    donations.sort(key=lambda item: item["timestamp"], reverse=True)
    donation_count = len(donations)
    donations = donations[:500]

    return render_template(
        "admin_dashboard.html",
        admin_username=session.get("flowtip_admin_username", "admin"),
        model_count=model_count,
        profile_count=profile_count,
        unused_codes=unused_codes,
        models=models,
        codes=codes,
        profiles=profiles,
        selected_profile=selected_profile,
        date_from=date_from,
        date_to=date_to,
        sender_query=sender_query,
        amount_query=amount_query,
        donations=donations,
        donation_count=donation_count,
        csrf_token=_csrf_token(),
        flashes=[],
    )
