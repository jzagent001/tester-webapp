from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import DATABASE_URL


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    # WAL lets readers and the (single) writer work at the same time, and waiting up to
    # 5 s for a lock beats failing with "database is locked" when two users save at once.
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def enable_wal(url: str) -> None:
    """WAL mode is a property of the database file, so set it once at startup."""
    if url.startswith("sqlite") and url not in ("sqlite://", "sqlite:///:memory:"):
        import sqlite3

        path = url.removeprefix("sqlite:///")
        with sqlite3.connect(path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # One shared connection, otherwise every session gets its own empty DB.
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _sqlite_pragmas)
    return engine


engine = make_engine(DATABASE_URL)


def create_db_and_tables(bind: Engine | None = None) -> None:
    from app import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(bind or engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
