# flask-postgres-rest

Small REST service: Flask + PostgreSQL, SQLAlchemy 2.0 ORM (psycopg 3 driver, built-in connection pool), pydantic
request validation, Alembic migrations. Python 3.11+ (developed on 3.13). Two resources: `/v1/surveys` and
`/v1/responses` (answers to a survey, with a foreign key to it).

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| POST | `/v1/surveys` | 201 + `Location` | 400 (validation), 413, 415 (not JSON) |
| GET | `/v1/surveys?limit=&offset=` | 200 `{items, limit, offset, next_offset}` | 400 |
| GET | `/v1/surveys/<id>` | 200 | 404 |
| POST | `/v1/responses` | 201 + `Location` | 400 (validation, bad JSON), 413, 415, 422 (unknown `survey_id`) |
| GET | `/v1/responses?survey_id=&limit=&offset=` | 200 `{items, limit, offset, next_offset}` | 400 |
| GET | `/v1/responses/<id>` | 200 | 404 |
| GET | `/healthz`, `/readyz` | 200 (readyz also checks the database) | 503 |

Fields (see [app/schemas.py](app/schemas.py)): survey `title` (1-200 chars, trimmed); response `survey_id` (int, must
exist), `respondent` (1-200 chars, trimmed), `rating` (int 1-5), `comment` (optional, <= 2000). Validation is strict, with
no type coercion (`"5"` and `true` are not ratings), unknown fields are rejected, and integers are bounded to the column
types, so out-of-range ids are a 404/400 rather than a database error. Query parameters must be plain ASCII integers (`1_0`, `+5`, ` 5 ` are rejected). Request bodies are capped at 64 KiB.

Every error is `application/problem+json` (RFC 9457), including Flask's own 404/405/413 (a 405 keeps its `Allow`
header). Unexpected exceptions are logged and returned as a generic 500; pool exhaustion is 503.

## Layout

| Path | Role |
| --- | --- |
| `app/__init__.py` | `create_app()` factory |
| `app/config.py`, `app/db.py` | config from the environment; SQLAlchemy engine and per-request session |
| `app/errors.py`, `app/http.py` | problem+json and error handlers; validation/pagination helpers |
| `app/models.py`, `app/schemas.py` | ORM models (also Alembic's `target_metadata`); pydantic request models |
| `app/routes/` | one Blueprint per resource, plus health |
| `migrations/`, `alembic.ini` | Alembic (migration SQL is hand-written; `--autogenerate` diffs the models) |
| `scripts/` | `migrate.py` (run migrations from Python, checkout only), `explain.py` (index experiment) |
| `tests/` | pytest suite (`conftest.py` holds the fixtures) |
| `pyproject.toml`, `uv.lock`, `.python-version` | dependencies, tooling config (ruff, mypy, pytest), the lockfile |
| `gunicorn.conf.py`, `.github/workflows/ci.yml` | serving; CI (Python 3.11-3.13 matrix) |
| `Dockerfile`, `compose.yaml`, `docker/initdb/` | container image and local stack |

## Run it

Requires [uv](https://docs.astral.sh/uv/) (`brew install uv`) for the Python environment.

```bash
export LC_ALL=en_US.UTF-8 PATH=/opt/homebrew/opt/postgresql@16/bin:$PATH
initdb -D .pgdata -U postgres --auth=trust
pg_ctl -D .pgdata -o "-p 5433 -k /tmp" -l .pgdata/server.log start
for db in surveys surveys_test surveys_explain; do createdb -h localhost -p 5433 -U postgres $db; done

uv sync                                        # creates .venv from uv.lock (Python 3.13 via .python-version)
export DATABASE_URL=postgresql://postgres@localhost:5433/surveys   # required: there is no default
uv run alembic upgrade head
FLASK_DEBUG=1 uv run flask --app app run      # dev server
uv run gunicorn "app:create_app()"           # production-style, configured by gunicorn.conf.py
```

Checks (CI runs the same four):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests scripts migrations/env.py
uv run pytest          # wipes and re-migrates surveys_test; refuses databases not ending in "_test"
uv run python -m scripts.explain   # seeds 500k rows in surveys_explain; refuses databases not ending in "_explain"
```

Dependencies are managed with uv. `uv.lock` pins every package (runtime and dev), `uv sync --locked` (CI, Dockerfile)
fails if it is out of date, and the image installs exactly the locked versions. To change them: edit `pyproject.toml`
(`[project] dependencies` for runtime, `[dependency-groups] dev` for tools), run `uv lock`, and commit both files;
`uv lock --upgrade` bumps everything within the declared ranges.

Environment variables: `DATABASE_URL` (required; the app and `alembic` refuse to start without it), `TEST_DATABASE_URL`, `EXPLAIN_DATABASE_URL`, `DB_POOL_SIZE` (5),
`DB_MAX_OVERFLOW` (5), `DB_POOL_TIMEOUT` (5 s), `WEB_CONCURRENCY` (gunicorn workers), `BIND`, `LOG_LEVEL`.
Each worker has its own pool, so keep `workers x (DB_POOL_SIZE + DB_MAX_OVERFLOW)` below Postgres `max_connections`.

Schema change: edit `app/models.py`, run `uv run alembic revision --autogenerate -m "describe it"`, review the
generated file (autogenerate misses CHECK constraints), then `alembic upgrade head`. `alembic check` and
`tests/test_migrations.py` fail if the models and migrations drift apart.

## Docker

```bash
docker compose up --build      # db + one-shot migration + API on http://localhost:8000
docker compose down -v         # stop and delete the database volume
```

[compose.yaml](compose.yaml) starts Postgres 16, runs `alembic upgrade head` once (`migrate`), then starts the API
(`api`, 2 gunicorn workers) after the migration succeeds. The [Dockerfile](Dockerfile) is multi-stage: the runtime image
(~300 MB) holds only the locked virtualenv (built with uv, which is not in the final image), the migrations and the gunicorn config, runs as a non-root user, and has a
`/healthz` healthcheck. It needs `DATABASE_URL` and does **not** migrate on start; run `alembic upgrade head` (the
`migrate` service) first, so several replicas never race to migrate.

The db port is published on `127.0.0.1:5434` (`DB_PORT` overrides) and `docker/initdb/` creates the `surveys_test` and
`surveys_explain` databases, so the host tools work against it too:

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5434/surveys_test uv run pytest
EXPLAIN_DATABASE_URL=postgresql://postgres:postgres@localhost:5434/surveys_explain uv run python -m scripts.explain
```

The compose credentials (`postgres` / `postgres`) are for local use only.

## EXPLAIN: `WHERE survey_id = 42 ORDER BY id LIMIT 51` on 500k rows

| | Plan | Buffers | Execution |
| --- | --- | --- | --- |
| Before (no index) | Parallel Index Scan on `responses_pkey`, filtering `survey_id = 42` (removed ~500k rows) | 9,117 | 19.5 ms |
| Index on `(survey_id)` | Bitmap Index Scan, then a Sort of ~100 rows | 104 | 0.11 ms |
| Index on `(survey_id, id)` (shipped) | Index Scan, rows already in `id` order, stops after 51 | 54 | 0.04 ms |

`scripts/explain.py` runs raw SQL for the bulk seed and the query, but the ORM emits the same statement shape
(`SELECT <columns> FROM responses WHERE survey_id = ... ORDER BY id LIMIT 51`), so the plans apply to the API.

Worth noting: the "before" plan was not a seq scan. Because of `ORDER BY id LIMIT`, the planner walked the
primary key in order hoping to hit matches early, which is still a full scan of the table when the filter is
selective. The single-column index fixes the filter; the composite index also removes the Sort, and it
doubles as the index for the `responses.survey_id` foreign key. Timings vary run to run; the shape does not.

## Deliberate omissions

- The local cluster uses trust auth as `postgres`; a real deployment would use a least-privilege role.
- Offset pagination: fine here, but keyset pagination on `id` scales better for deep pages.
- No update or delete endpoints, no authentication, no rate limiting.
- The image is built for local use and CI: no registry publishing, image scanning or pinned base-image digests (the Python packages are locked; the `python`/`postgres` base images are version tags). The CI workflow has not run on GitHub yet; its commands were run locally on Python 3.11, 3.12 and 3.13.

## Compared with C# / TypeScript

Flask is much thinner than ASP.NET Core: there is no DI container or model binding, so I wired validation (pydantic),
the SQLAlchemy session (one per request, closed in a teardown hook) and migrations (Alembic) together myself, and
SQLAlchemy plays the role of EF Core but with an explicit unit of work (`add`, `commit`) and no compile-time checking
of queries, which means correctness lives in my tests and mypy rather than the compiler.
The Python-specific surprises were that `bool` is a subclass of `int` (so `rating: true` passes a naive check, and
pydantic needs strict mode to reject it), and that Postgres planned an ordered primary-key scan rather than a seq
scan until I added the index.
