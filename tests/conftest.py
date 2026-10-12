import os
from collections.abc import Iterator

import psycopg
import pytest
from flask import Flask
from flask.testing import FlaskClient
from psycopg.conninfo import conninfo_to_dict

from app import create_app
from scripts import migrate

TEST_DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5433/surveys_test")


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Start from an empty test database; prove the migration goes up, down and up again."""
    dbname = str(conninfo_to_dict(TEST_DSN).get("dbname", ""))
    if not dbname.endswith("_test"):  # this fixture drops everything in the database
        pytest.exit(f"refusing to run: database {dbname!r} does not end in '_test'", returncode=2)
    try:
        conn = psycopg.connect(TEST_DSN, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as e:
        pytest.exit(f"PostgreSQL not reachable at TEST_DATABASE_URL ({TEST_DSN}): {e}", returncode=2)
    with conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    migrate.upgrade(TEST_DSN)
    migrate.downgrade(TEST_DSN)
    migrate.upgrade(TEST_DSN)


@pytest.fixture
def app() -> Iterator[Flask]:
    with psycopg.connect(TEST_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE responses, surveys RESTART IDENTITY")
    app = create_app({"DATABASE_URL": TEST_DSN, "TESTING": True})
    yield app
    app.extensions["engine"].dispose()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """A client with two surveys already created (ids 1 and 2)."""
    c = app.test_client()
    for title in ("First survey", "Second survey"):
        assert c.post("/v1/surveys", json={"title": title}).status_code == 201
    return c
