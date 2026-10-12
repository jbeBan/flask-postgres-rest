from typing import Any

from flask import Flask

from app.config import default_config
from app.db import init_db
from app.errors import register_error_handlers
from app.routes import health, responses, surveys


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(default_config())
    app.config.update(config or {})

    init_db(app)
    register_error_handlers(app)
    for module in (health, surveys, responses):
        app.register_blueprint(module.bp)
    return app
