from typing import Any

from flask import Flask, Response, jsonify
from sqlalchemy.exc import TimeoutError as PoolTimeout
from werkzeug.exceptions import HTTPException


def problem(status: int, title: str, **extra: Any) -> Response:
    """RFC 9457 problem details response."""
    resp = jsonify({"type": "about:blank", "title": title, "status": status, **extra})
    resp.status_code = status
    resp.mimetype = "application/problem+json"
    return resp


class ProblemError(Exception):
    """Raised by helpers that must stop the request with a problem+json response."""

    def __init__(self, status: int, title: str, **extra: Any) -> None:
        super().__init__(title)
        self.status, self.title, self.extra = status, title, extra


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ProblemError)
    def problem_error(e: ProblemError) -> Response:
        return problem(e.status, e.title, **e.extra)

    @app.errorhandler(HTTPException)
    def http_error(e: HTTPException) -> Response:
        # Covers Flask's own 404/405/413/... so every error is JSON.
        resp = problem(e.code or 500, e.name, detail=e.description)
        for key, value in e.get_headers():
            if key.lower() != "content-type":  # keeps e.g. Allow on a 405
                resp.headers[key] = value
        return resp

    @app.errorhandler(PoolTimeout)
    def pool_exhausted(_e: PoolTimeout) -> Response:
        app.logger.error("database connection pool exhausted")
        return problem(503, "Service Unavailable", detail="database is busy")

    @app.errorhandler(Exception)
    def unexpected(_e: Exception) -> Response:
        app.logger.exception("unhandled exception")
        return problem(500, "Internal Server Error")
