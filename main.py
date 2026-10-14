from flask import Flask
from flask_cors import CORS
import threading

from app.panel_app import panel_bp
from app.vip_app import vip_bp
from app.stats_app import stats_bp
from app.goal_app import goal_bp
from app.rules_app import rules_bp
from app.reactions_app import reactions_bp
from app.obs_app import obs_bp
from app.lovense_app import lovense_bp
from services.maintenance_service import periodic_backup_cleanup

from config import CONFIG
from services.database import init_db
from app.lovense_test_app import lovense_test_bp
from app.admin_app import admin_bp
import os


def create_app():
    app = Flask(__name__)
    app.secret_key = CONFIG["secret_key"]
    app.config.update(
        # Production is expected to run behind HTTPS. Set FLOWTIP_COOKIE_SECURE=false
        # only for local development over plain HTTP.
        SESSION_COOKIE_SECURE=os.environ.get("FLOWTIP_COOKIE_SECURE", "true").lower() in ("1", "true", "yes", "on"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=1800,
    )
    CORS(app)

    # 🔥 Регистрируем все blueprints
    app.register_blueprint(panel_bp)
    app.register_blueprint(vip_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(goal_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(reactions_bp)
    app.register_blueprint(obs_bp)
    app.register_blueprint(lovense_bp)
    app.register_blueprint(lovense_test_bp)
    app.register_blueprint(admin_bp)

    # 🔧 Запускаем фоновую очистку
    threading.Thread(
        target=periodic_backup_cleanup,
        args=(5,),
        daemon=True
    ).start()

    return app
