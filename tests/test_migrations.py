"""Migrations build exactly the schema the models describe, and upgrade old data safely."""

import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from app.migrate import alembic_config, upgrade


def _url(path) -> str:
    return f"sqlite:///{path}"


def _diff(path):
    engine = create_engine(_url(path))
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    engine.dispose()
    return diff


def _pre_users_db(path, with_version_table=True):
    """A database as the app made it before users existed, with some data."""
    command.upgrade(alembic_config(_url(path)), "0001")
    db = sqlite3.connect(path)
    db.executescript("""
        INSERT INTO bank VALUES (1, 'Networking', '', 20, NULL, '2026-01-01 00:00:00');
        INSERT INTO module VALUES (1, 1, 'DNS', 0);
        INSERT INTO knowledge_point VALUES (1, 1, 'Records', '', 0);
        INSERT INTO question VALUES (1, 1, 1, 1, 'Q?', '', '2026-01-01 00:00:00');
        INSERT INTO choice VALUES (1, 1, 0, 'a', 1), (2, 1, 1, 'b', 0);
        INSERT INTO attempt VALUES (1, 1, '', '2026-01-01 00:00:00', NULL);
        INSERT INTO attempt_item VALUES (1, 1, 1, 1, 1, 1, '1', 1, '2026-01-01 00:00:00');
    """)
    if not with_version_table:  # like a database made by create_all before migrations
        db.execute("DROP TABLE alembic_version")
    db.commit()
    db.close()


def _rows(path, sql):
    db = sqlite3.connect(path)
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


def test_fresh_database_matches_models(tmp_path):
    path = tmp_path / "fresh.db"
    upgrade(_url(path))
    assert _diff(path) == []


@pytest.mark.parametrize("with_version_table", [True, False], ids=["migrated", "pre-migrations"])
def test_existing_data_gets_an_owner(tmp_path, monkeypatch, with_version_table):
    path = tmp_path / "old.db"
    _pre_users_db(path, with_version_table)
    monkeypatch.setenv("OWNER_EMAIL", "Owner@Example.com")
    upgrade(_url(path))

    assert _diff(path) == []
    assert _rows(path, "SELECT id, email FROM app_user") == [(1, "owner@example.com")]
    assert _rows(path, "SELECT id, owner_id, name FROM bank") == [(1, 1, "Networking")]
    assert _rows(path, "SELECT id, bank_id, user_id FROM attempt") == [(1, 1, 1)]
    for table, n in [("module", 1), ("knowledge_point", 1), ("question", 1), ("choice", 2), ("attempt_item", 1)]:
        assert _rows(path, f"SELECT COUNT(*) FROM {table}") == [(n,)], table
    assert _rows(path, "PRAGMA foreign_key_check") == []


def test_refuses_without_owner_email_and_changes_nothing(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    _pre_users_db(path)
    monkeypatch.delenv("OWNER_EMAIL", raising=False)
    monkeypatch.delenv("SINGLE_USER_EMAIL", raising=False)
    before = _rows(path, "SELECT name, sql FROM sqlite_master ORDER BY name")

    with pytest.raises(RuntimeError, match="OWNER_EMAIL"):
        upgrade(_url(path))

    assert _rows(path, "SELECT name, sql FROM sqlite_master ORDER BY name") == before
    assert _rows(path, "SELECT version_num FROM alembic_version") == [("0001",)]


def test_tolerates_empty_app_user_left_by_create_all(tmp_path, monkeypatch):
    """Before migrations, a dev-server reload ran create_all, which adds new tables only."""
    path = tmp_path / "old.db"
    _pre_users_db(path)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE app_user (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL UNIQUE, "
               "created_at DATETIME NOT NULL, last_seen_at DATETIME NOT NULL)")
    db.commit()
    db.close()
    monkeypatch.setenv("OWNER_EMAIL", "owner@example.com")
    upgrade(_url(path))
    assert _diff(path) == []


def test_upgrade_is_idempotent(tmp_path):
    path = tmp_path / "fresh.db"
    upgrade(_url(path))
    upgrade(_url(path))
    assert _rows(path, "SELECT version_num FROM alembic_version") == [("0002",)]
