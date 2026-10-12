from flask import Flask, current_app, g
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import sqlalchemy_url


def init_db(app: Flask) -> None:
    dsn = app.config.get("DATABASE_URL")
    if not dsn:
        # Fail at startup (gunicorn exits, the container stops) rather than serving 503s from a dead default.
        raise RuntimeError("DATABASE_URL is not set (e.g. postgresql://user:password@host:5432/dbname)")
    engine = create_engine(
        sqlalchemy_url(dsn),
        pool_size=app.config["DB_POOL_SIZE"],
        max_overflow=app.config["DB_MAX_OVERFLOW"],
        pool_timeout=app.config["DB_POOL_TIMEOUT"],
        pool_pre_ping=True,
    )
    app.extensions["engine"] = engine
    # expire_on_commit=False: models stay readable after commit, so views can serialize them.
    app.extensions["session_factory"] = sessionmaker(engine, expire_on_commit=False)

    @app.teardown_appcontext
    def close_session(_exc: BaseException | None) -> None:
        db = g.pop("session", None)
        if db is not None:
            db.close()  # rolls back anything uncommitted and returns the connection to the pool


def session() -> Session:
    """The request's ORM session (one per request)."""
    if "session" not in g:
        g.session = current_app.extensions["session_factory"]()
    session: Session = g.session
    return session
