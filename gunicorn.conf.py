# Used automatically by `gunicorn "app:create_app()"` from the project root.
# WEB_CONCURRENCY (read by gunicorn itself) sets the worker count; each worker has its own DB pool,
# so keep workers x (DB_POOL_SIZE + DB_MAX_OVERFLOW) below Postgres max_connections.
import os

bind = os.environ.get("BIND", "127.0.0.1:8000")
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
timeout = 30
graceful_timeout = 30
