import os

# Largest values the column types can hold; inputs beyond these are rejected up front
# instead of reaching Postgres as "out of range" errors.
INT32_MAX = 2**31 - 1
INT64_MAX = 2**63 - 1


def database_url() -> str:
    """DATABASE_URL from the environment. There is deliberately no default: a missing value must stop the
    process at startup instead of quietly connecting to some localhost database."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (e.g. postgresql://user:password@host:5432/dbname)")
    return url


def sqlalchemy_url(dsn: str) -> str:
    # Plain postgresql:// would make SQLAlchemy look for psycopg2; we use psycopg 3.
    return dsn.replace("postgresql://", "postgresql+psycopg://", 1)


def default_config() -> dict[str, object]:
    """Flask config, read from the environment once at startup."""
    return {
        # Optional here so tests can pass their own; init_db() refuses to start without one.
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        # Per-process limits: total connections ~= gunicorn workers x (pool size + overflow).
        "DB_POOL_SIZE": int(os.environ.get("DB_POOL_SIZE", "5")),
        "DB_MAX_OVERFLOW": int(os.environ.get("DB_MAX_OVERFLOW", "5")),
        "DB_POOL_TIMEOUT": float(os.environ.get("DB_POOL_TIMEOUT", "5")),
        "MAX_CONTENT_LENGTH": 64 * 1024,  # request bodies here are tiny; Flask answers 413 beyond this
    }
