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
from app.stats_app import stats_bp
from config import CONFIG


def create_app():
    app = Flask(__name__)
    app.secret_key = CONFIG["secret_key"]
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
    app.register_blueprint(stats_bp)
    return app


def run_flask():
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    profile_keys = list(CONFIG["profiles"].keys())

    threading.Thread(
        target=periodic_backup_cleanup,
        args=(5,),
        daemon=True
    ).start()

    # 🔥 Запускаем WebSocket‑сервер в отдельном потоке
    threading.Thread(
        target=run_websocket_server,
        args=(profile_keys,),
        daemon=True
    ).start()

    # 🔥 Запускаем Flask
    run_flask()
