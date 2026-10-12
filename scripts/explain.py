"""Seed ~500k rows, then EXPLAIN ANALYZE the survey_id filter in three states:
no index, a single-column index, and the composite index the app ships with.

This script wipes the database's public schema and re-runs the migrations, so it refuses to run unless
the target database name ends in "_explain".

Usage: .venv/bin/python -m scripts.explain   (EXPLAIN_DATABASE_URL overrides the default DSN)
"""

import os
import sys

import psycopg
from psycopg import Cursor
from psycopg.conninfo import conninfo_to_dict

from scripts import migrate

DSN = os.environ.get("EXPLAIN_DATABASE_URL", "postgresql://postgres@localhost:5433/surveys_explain")
ROWS = 500_000
SURVEYS = 5_000  # ~100 rows per survey, so the filter is highly selective
# Same shape as the statement the ORM emits for GET /v1/responses?survey_id=42 (limit + 1 rows)
QUERY = "SELECT * FROM responses WHERE survey_id = 42 ORDER BY id LIMIT 51"


def explain(cur: Cursor, label: str) -> None:
    print(f"\n=== {label} ===")
    cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + QUERY)
    for (line,) in cur.fetchall():
        print(line)


def main() -> None:
    dbname = str(conninfo_to_dict(DSN).get("dbname", ""))
    if not dbname.endswith("_explain"):
        sys.exit(
            f"refusing to run: database {dbname!r} does not end in '_explain' (this script wipes the schema)"
        )

    with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE")
        cur.execute("CREATE SCHEMA public")
        migrate.upgrade(DSN)
        cur.execute("DROP INDEX idx_responses_survey_id_id")  # measure without it first
        cur.execute(
            "INSERT INTO surveys (title) SELECT 'Survey ' || g FROM generate_series(1, %s) AS g",
            (SURVEYS,),
        )
        cur.execute(
            """
            INSERT INTO responses (survey_id, respondent, rating, comment)
            SELECT 1 + (random() * %s)::int, 'user' || g || '@example.com',
                   1 + (random() * 4)::int, md5(g::text)
            FROM generate_series(1, %s) AS g
            """,
            (SURVEYS - 1, ROWS),
        )
        cur.execute("ANALYZE responses")
        explain(cur, "BEFORE: no index on survey_id")

        cur.execute("CREATE INDEX idx_single ON responses (survey_id)")
        cur.execute("ANALYZE responses")
        explain(cur, "AFTER 1: single-column index (survey_id)")

        cur.execute("DROP INDEX idx_single")
        cur.execute("CREATE INDEX idx_responses_survey_id_id ON responses (survey_id, id)")
        cur.execute("ANALYZE responses")
        explain(cur, "AFTER 2: composite index (survey_id, id)  <- shipped in the migration")


if __name__ == "__main__":
    main()
