# syntax=docker/dockerfile:1

# ---- build: install exactly the locked dependencies, then the app, into a virtualenv ----
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /src
# Dependencies first (cached until pyproject.toml / uv.lock change); --locked fails if the lock is stale.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app
RUN uv sync --locked --no-dev --no-editable

# ---- runtime: venv + migrations only, no uv, no compilers, no tests, no root ----
FROM python:3.13-slim
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BIND=0.0.0.0:8000
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /opt/venv /opt/venv
WORKDIR /srv
COPY alembic.ini gunicorn.conf.py ./
COPY migrations ./migrations
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
# DATABASE_URL is required: the app exits at startup without it. Run `alembic upgrade head` separately
# (see the migrate service in compose.yaml) before starting.
CMD ["gunicorn", "app:create_app()"]
