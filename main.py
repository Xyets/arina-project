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
from app.ws_app import run_websocket_server
from services.maintenance_service import periodic_backup_cleanup

from config import CONFIG


def create_app():
    app = Flask(__name__)
    app.secret_key = CONFIG["secret_key"]
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="None"
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

    # 🔥 Запускаем WebSocket сервер (ВАЖНО: внутри create_app)
    profile_keys = list(CONFIG["profiles"].keys())

    threading.Thread(
        target=run_websocket_server,
        daemon=True
    ).start()


    # 🔧 Запускаем фоновую очистку
    threading.Thread(
        target=periodic_backup_cleanup,
        args=(5,),
        daemon=True
    ).start()

    return app
