import pytest

from app import create_app
from app.config import database_url
from tests.conftest import TEST_DSN


def test_app_refuses_to_start_without_a_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        create_app()


def test_explicit_config_does_not_need_the_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = create_app({"DATABASE_URL": TEST_DSN})
    app.extensions["engine"].dispose()


def test_environment_variable_is_used_when_no_override_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", TEST_DSN)
    assert database_url() == TEST_DSN
    app = create_app()
    assert app.config["DATABASE_URL"] == TEST_DSN
    app.extensions["engine"].dispose()


def test_database_url_helper_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        database_url()  # what `alembic upgrade head` calls
