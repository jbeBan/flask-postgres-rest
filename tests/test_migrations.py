import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, create_engine, inspect

from app.config import sqlalchemy_url
from app.models import Base
from tests.conftest import TEST_DSN


def test_models_match_migrations() -> None:
    """The ORM models and the hand-written migration describe the same schema."""
    engine = create_engine(sqlalchemy_url(TEST_DSN))
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_check_constraints_in_models_and_migration_have_the_same_names() -> None:
    """compare_metadata ignores CHECK constraints, so compare their names explicitly."""
    engine = create_engine(sqlalchemy_url(TEST_DSN))
    inspector = inspect(engine)
    for name, table in Base.metadata.tables.items():
        in_models = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
        in_database = {c["name"] for c in inspector.get_check_constraints(name)}
        assert in_models == in_database, f"CHECK constraints differ on {name}"
    engine.dispose()


def new_survey(conn: psycopg.Connection, title: str = "placeholder") -> int:
    row = conn.execute("INSERT INTO surveys (title) VALUES (%s) RETURNING id", (title,)).fetchone()
    assert row is not None
    return int(row[0])


RESPONSE = (
    "INSERT INTO responses (survey_id, respondent, rating, comment) "
    "VALUES (%(sid)s, %(who)s, %(rating)s, %(comment)s)"
)
VALID = {"who": "a", "rating": 3, "comment": None}


@pytest.mark.parametrize(
    ("statement", "params", "constraint"),
    [
        ("INSERT INTO surveys (title) VALUES (%(who)s)", {"who": ""}, "surveys_title_check"),
        ("INSERT INTO surveys (title) VALUES (%(who)s)", {"who": "x" * 201}, "surveys_title_check"),
        (RESPONSE, {**VALID, "who": ""}, "responses_respondent_check"),
        (RESPONSE, {**VALID, "who": "x" * 201}, "responses_respondent_check"),
        (RESPONSE, {**VALID, "rating": 0}, "responses_rating_check"),
        (RESPONSE, {**VALID, "rating": 6}, "responses_rating_check"),
        (RESPONSE, {**VALID, "comment": "x" * 2001}, "responses_comment_check"),
    ],
)
def test_database_rejects_values_the_api_would_never_send(
    statement: str, params: dict[str, object], constraint: str
) -> None:
    """The CHECK constraints are the second line of defence behind pydantic; prove they bite on their own."""
    with psycopg.connect(TEST_DSN) as conn:  # one transaction, rolled back on exit: leaves nothing behind
        params = {**params, "sid": new_survey(conn)}
        with pytest.raises(psycopg.errors.CheckViolation) as exc:
            conn.execute(statement, params)
        assert exc.value.diag.constraint_name == constraint


def test_database_accepts_boundary_values() -> None:
    with psycopg.connect(TEST_DSN) as conn:
        sid = new_survey(conn, "x" * 200)
        for rating in (1, 5):
            params = {"sid": sid, "who": "x" * 200, "rating": rating, "comment": "x" * 2000}
            conn.execute(RESPONSE, params)
