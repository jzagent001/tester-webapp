"""Alembic environment.

The database URL comes from `app.config.DATABASE_URL` unless the caller sets
`sqlalchemy.url` on the Alembic config (app/migrate.py and the tests do).

Migrations run on a plain engine, deliberately WITHOUT the app's
`PRAGMA foreign_keys=ON` listener: SQLite table rebuilds (create new table,
copy, drop old, rename) would otherwise cascade-delete child rows when the old
table is dropped. Each migration that rebuilds tables runs `PRAGMA foreign_key_check`
afterwards instead.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, event
from sqlmodel import SQLModel

from app import models  # noqa: F401  (registers the tables on SQLModel.metadata)
from app.config import DATABASE_URL

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _transactional_sqlite(engine) -> None:
    """Make every migration all-or-nothing on SQLite.

    Python's sqlite3 driver only opens a transaction before INSERT/UPDATE/DELETE, so
    a CREATE TABLE that runs first is committed immediately and survives a later
    failure. Taking over transaction control (the recipe from the SQLAlchemy docs)
    makes a failed migration leave the database exactly as it was.
    """

    @event.listens_for(engine, "connect")
    def _no_driver_transactions(dbapi_connection, _record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(connection):
        connection.exec_driver_sql("BEGIN")


def run_migrations_online() -> None:
    engine = create_engine(_url())
    if engine.dialect.name == "sqlite":
        _transactional_sqlite(engine)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
