from __future__ import annotations

import os

from flask import Flask

from config import Config
from database import db
from routes.chat import chat_bp
from routes.dashboard import dashboard_bp
from routes.environments import environments_bp
from routes.rag import rag_bp
from routes.settings import settings_bp
from services.settings_service import ensure_default_settings


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    (app.config["DATA_DIR"] / "environments").mkdir(parents=True, exist_ok=True)
    db.init_app(app)

    with app.app_context():
        import models  # noqa: F401

        db.create_all()
        ensure_default_settings(db)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(environments_bp)
    app.register_blueprint(rag_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(chat_bp)
    return app


app = create_app()


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=5051, debug=debug_enabled)
