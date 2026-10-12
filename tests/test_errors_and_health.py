import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from tests.conftest import TEST_DSN


def test_405_is_json_and_keeps_the_allow_header(client: FlaskClient) -> None:
    resp = client.delete("/v1/responses/1")
    assert resp.status_code == 405
    assert resp.mimetype == "application/problem+json"
    assert "GET" in resp.headers["Allow"]


def test_unknown_route_is_json_404(client: FlaskClient) -> None:
    resp = client.get("/nope")
    assert resp.status_code == 404
    assert resp.mimetype == "application/problem+json"


def test_oversized_body_returns_413(client: FlaskClient) -> None:
    resp = client.post("/v1/responses", data=b"x" * (64 * 1024 + 1), content_type="application/json")
    assert resp.status_code == 413
    assert resp.mimetype == "application/problem+json"


def test_unexpected_exception_returns_json_500_without_details(app: Flask) -> None:
    @app.get("/boom")
    def boom() -> str:
        raise RuntimeError("secret internals")

    app.config["PROPAGATE_EXCEPTIONS"] = False
    resp = app.test_client().get("/boom")
    assert resp.status_code == 500
    assert resp.mimetype == "application/problem+json"
    assert "secret" not in resp.get_data(as_text=True)


def test_liveness_and_readiness(client: FlaskClient) -> None:
    assert client.get("/healthz").get_json() == {"status": "ok"}
    assert client.get("/readyz").get_json() == {"status": "ok"}


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://postgres@127.0.0.1:1/surveys_test",  # nothing listens on port 1: connection refused
        TEST_DSN.rsplit("/", 1)[0] + "/does_not_exist",  # server is up but the database is missing
    ],
    ids=["server-unreachable", "database-missing"],
)
def test_readiness_is_503_when_the_database_is_down(dsn: str) -> None:
    dead = create_app({"DATABASE_URL": dsn})
    try:
        resp = dead.test_client().get("/readyz")
        assert resp.status_code == 503
        assert resp.mimetype == "application/problem+json"
        assert dead.test_client().get("/healthz").status_code == 200  # liveness doesn't need the DB
    finally:
        dead.extensions["engine"].dispose()
