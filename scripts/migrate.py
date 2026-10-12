"""Run Alembic migrations from Python (tests, explain.py); the CLI works too.

Lives in scripts/, not app/: it finds alembic.ini relative to the source checkout, so it must not ship in
the installed package (where that path does not exist).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent.parent


def _config(dsn: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", dsn.replace("%", "%%"))  # configparser interpolation
    return cfg


def upgrade(dsn: str, revision: str = "head") -> None:
    command.upgrade(_config(dsn), revision)


def downgrade(dsn: str, revision: str = "base") -> None:
    command.downgrade(_config(dsn), revision)
