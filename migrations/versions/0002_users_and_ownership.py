"""users and ownership

Adds the app_user table, makes every bank belong to an owner (bank names become
unique per owner instead of globally) and records who took each test.

Existing banks and attempts are given to one user, whose email comes from the
OWNER_EMAIL environment variable, falling back to SINGLE_USER_EMAIL. The
migration refuses to run on a database that has banks if neither is set.

SQLite can't add NOT NULL foreign-key columns or drop an unnamed UNIQUE
constraint in place, so `bank` and `attempt` are rebuilt: create *_new, copy,
drop the old table, rename. migrations/env.py runs without foreign-key
enforcement so dropping the old table doesn't cascade-delete child rows; the
result is verified with PRAGMA foreign_key_check.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15
"""

import os
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _owner_email() -> str:
    email = (os.environ.get("OWNER_EMAIL") or os.environ.get("SINGLE_USER_EMAIL") or "").strip()
    if not email:
        raise RuntimeError(
            "This database already has question banks, and they need an owner. "
            "Set OWNER_EMAIL to the email you will sign in with, then start the app again."
        )
    return email.lower()


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "sqlite":
        raise NotImplementedError("This migration is written for SQLite.")

    # An empty app_user can already exist: before migrations, the app ran create_all at
    # startup, which adds new tables (but can't change existing ones) on a code reload.
    if sa.inspect(conn).has_table("app_user"):
        if conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM app_user)")).scalar():
            raise RuntimeError("app_user already has rows; this database needs manual attention.")
        op.drop_table("app_user")
    op.create_table(
        "app_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    owner_id = None
    if conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM bank)")).scalar():
        # Same text format SQLAlchemy uses for DATETIME columns on SQLite (UTC).
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
        conn.execute(
            sa.text("INSERT INTO app_user (email, created_at, last_seen_at) VALUES (:e, :t, :t)"),
            {"e": _owner_email(), "t": now},
        )
        owner_id = conn.execute(sa.text("SELECT id FROM app_user")).scalar_one()

    op.execute("""
        CREATE TABLE bank_new (
            id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            quiz_length INTEGER NOT NULL,
            pass_mark INTEGER,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (owner_id, name),
            FOREIGN KEY(owner_id) REFERENCES app_user (id) ON DELETE CASCADE
        )""")
    conn.execute(
        sa.text("""
            INSERT INTO bank_new (id, owner_id, name, description, quiz_length, pass_mark, created_at)
            SELECT id, :owner, name, description, quiz_length, pass_mark, created_at FROM bank"""),
        {"owner": owner_id},
    )
    op.execute("DROP TABLE bank")
    op.execute("ALTER TABLE bank_new RENAME TO bank")
    op.execute("CREATE INDEX ix_bank_owner_id ON bank (owner_id)")

    op.execute("""
        CREATE TABLE attempt_new (
            id INTEGER NOT NULL,
            bank_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            scope VARCHAR NOT NULL,
            started_at DATETIME NOT NULL,
            finished_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(bank_id) REFERENCES bank (id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES app_user (id) ON DELETE CASCADE
        )""")
    # Every existing attempt was taken by the (single) owner of its bank.
    op.execute("""
        INSERT INTO attempt_new (id, bank_id, user_id, scope, started_at, finished_at)
        SELECT a.id, a.bank_id, b.owner_id, a.scope, a.started_at, a.finished_at
        FROM attempt a JOIN bank b ON b.id = a.bank_id""")
    op.execute("DROP TABLE attempt")
    op.execute("ALTER TABLE attempt_new RENAME TO attempt")
    op.execute("CREATE INDEX ix_attempt_bank_id ON attempt (bank_id)")
    op.execute("CREATE INDEX ix_attempt_user_id ON attempt (user_id)")

    problems = conn.execute(sa.text("PRAGMA foreign_key_check")).fetchall()
    if problems:
        raise RuntimeError(f"Foreign key check failed after migration: {problems[:5]}")


def downgrade() -> None:
    raise NotImplementedError("Restore a backup taken before upgrading instead.")
