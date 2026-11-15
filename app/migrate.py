"""Bring the database schema up to date. Runs at startup; also `uv run python -m app.migrate`.

Databases created before migrations existed (by `create_all`, with no
`alembic_version` table) are stamped as the 0001 baseline first, then upgraded.
"""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import BASE_DIR, DATABASE_URL

BASELINE = "0001"


def alembic_config(url: str) -> Config:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logging"] = False  # keep the app's / uvicorn's logging
    return config


def upgrade(url: str = DATABASE_URL) -> None:
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    config = alembic_config(url)
    if "bank" in tables and "alembic_version" not in tables:
        command.stamp(config, BASELINE)
    command.upgrade(config, "head")


if __name__ == "__main__":
    upgrade()
    print("Database is up to date.")
