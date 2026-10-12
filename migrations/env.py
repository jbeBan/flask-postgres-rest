from alembic import context
from sqlalchemy import create_engine, pool

from app.config import database_url, sqlalchemy_url
from app.models import Base

config = context.config
# Lets `alembic revision --autogenerate` diff the models against the database.
target_metadata = Base.metadata


def url() -> str:
    # scripts/migrate.py injects the URL for tests; the CLI falls back to DATABASE_URL.
    return sqlalchemy_url(config.get_main_option("sqlalchemy.url") or database_url())


def run_migrations_offline() -> None:
    context.configure(url=url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
