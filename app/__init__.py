"""Secret Santa web app — application factory."""
import logging
import os

from dotenv import load_dotenv
from flask import Flask

from .models import db

DEFAULT_DATABASE_URL = "postgresql+psycopg://santa:santa@localhost:5432/secret_santa"


def normalize_db_url(url: str) -> str:
    """Use the psycopg 3 driver, and accept postgres:// URLs from hosts like Render/Heroku."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        SQLALCHEMY_DATABASE_URI=normalize_db_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        # Public base URL used in WhatsApp links, e.g. https://santa.example.com
        APP_BASE_URL=os.getenv("APP_BASE_URL", "").rstrip("/"),
        # "console" logs messages instead of sending; "meta" uses the WhatsApp Cloud API
        WHATSAPP_PROVIDER=os.getenv("WHATSAPP_PROVIDER", "console"),
        WHATSAPP_TOKEN=os.getenv("WHATSAPP_TOKEN", ""),
        WHATSAPP_PHONE_NUMBER_ID=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
        DEFAULT_COUNTRY_CODE=os.getenv("DEFAULT_COUNTRY_CODE", "254"),
    )
    if test_config:
        app.config.update(test_config)
        app.config["SQLALCHEMY_DATABASE_URI"] = normalize_db_url(
            app.config["SQLALCHEMY_DATABASE_URI"]
        )

    logging.basicConfig(level=logging.INFO)
    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

    return app
