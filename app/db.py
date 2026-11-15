from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import DATABASE_URL


def _enable_foreign_keys(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # One shared connection, otherwise every session gets its own empty DB.
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_foreign_keys)
    return engine


engine = make_engine(DATABASE_URL)


def create_db_and_tables(bind: Engine | None = None) -> None:
    from app import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(bind or engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
