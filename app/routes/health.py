from flask import Blueprint, Response, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import session
from app.errors import problem

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def liveness() -> Response:
    """The process is up (no dependencies checked)."""
    return jsonify(status="ok")


@bp.get("/readyz")
def readiness() -> Response:
    """The process can serve traffic: the database answers."""
    try:
        session().execute(text("SELECT 1"))
    except SQLAlchemyError:
        return problem(503, "Service Unavailable", detail="database unavailable")
    return jsonify(status="ok")
