"""Database tables.

Every Bank has an owner (a User, identified by email; see app/auth.py) and only its
owner can see or change it. Test attempts belong to the user who took them.

A Bank (one exam or subject) holds Modules, each Module holds KnowledgePoints.
Every Question belongs to a bank and is classified at one of three levels:

    module_id=None, knowledge_point_id=None   general question for the bank
    module_id=M,    knowledge_point_id=None   general question within module M
    module_id=M,    knowledge_point_id=K      knowledge point K (which belongs to M)

Deleting a module or knowledge point leaves its questions in place, reclassified
as general (the foreign keys are ON DELETE SET NULL).
"""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _ids(text: str) -> list[int]:
    return [int(x) for x in text.split(",") if x]


class User(SQLModel, table=True):
    """Someone who signed in. Created automatically on first request; no passwords here."""

    __tablename__ = "app_user"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True)  # lower-case
    created_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class Bank(SQLModel, table=True):
    # Names are unique per owner (the app also compares them case-insensitively).
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="app_user.id", ondelete="CASCADE", index=True)
    name: str
    description: str = ""
    quiz_length: int = 20
    pass_mark: int | None = None  # percent; None means no pass/fail verdict
    created_at: datetime = Field(default_factory=utcnow)

    modules: list["Module"] = Relationship(
        back_populates="bank",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "Module.position",
        },
    )


class Module(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("bank_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    bank_id: int = Field(foreign_key="bank.id", ondelete="CASCADE", index=True)
    name: str
    position: int = 0

    bank: Bank = Relationship(back_populates="modules")
    points: list["KnowledgePoint"] = Relationship(
        back_populates="module",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "KnowledgePoint.position",
        },
    )


class KnowledgePoint(SQLModel, table=True):
    __tablename__ = "knowledge_point"
    __table_args__ = (UniqueConstraint("module_id", "name"),)

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", ondelete="CASCADE", index=True)
    name: str
    description: str = ""
    position: int = 0

    module: Module = Relationship(back_populates="points")


class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    bank_id: int = Field(foreign_key="bank.id", ondelete="CASCADE", index=True)
    module_id: int | None = Field(
        default=None, foreign_key="module.id", ondelete="SET NULL", index=True
    )
    knowledge_point_id: int | None = Field(
        default=None, foreign_key="knowledge_point.id", ondelete="SET NULL", index=True
    )
    text: str
    explanation: str = ""
    created_at: datetime = Field(default_factory=utcnow)

    module: Module | None = Relationship()
    knowledge_point: KnowledgePoint | None = Relationship()
    choices: list["Choice"] = Relationship(
        back_populates="question",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Choice.position"},
    )

    @property
    def correct_ids(self) -> set[int]:
        return {c.id for c in self.choices if c.is_correct and c.id is not None}

    @property
    def topic_label(self) -> str:
        if self.module is None:
            return "General"
        if self.knowledge_point is None:
            return f"{self.module.name} › General"
        return f"{self.module.name} › {self.knowledge_point.name}"


class Choice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", ondelete="CASCADE", index=True)
    position: int = 0
    text: str
    is_correct: bool = False

    question: Question = Relationship(back_populates="choices")


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    bank_id: int = Field(foreign_key="bank.id", ondelete="CASCADE", index=True)
    user_id: int = Field(foreign_key="app_user.id", ondelete="CASCADE", index=True)  # who took it
    scope: str = ""  # human-readable description of what was selected; "" means everything
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None

    bank: Bank = Relationship()
    items: list["AttemptItem"] = Relationship(
        back_populates="attempt",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "AttemptItem.position"},
    )

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def score(self) -> int:
        return sum(1 for i in self.items if i.is_correct)

    @property
    def answered(self) -> int:
        return sum(1 for i in self.items if i.is_answered)


class AttemptItem(SQLModel, table=True):
    """One question in a test, with its classification copied at the time the test started.

    Deliberately no foreign keys to question/module/knowledge point: a test's history
    and per-topic scores survive editing or deleting them.
    """

    __tablename__ = "attempt_item"

    id: int | None = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempt.id", ondelete="CASCADE", index=True)
    position: int  # 1-based order in the test
    question_id: int = Field(index=True)
    module_id: int | None = None
    knowledge_point_id: int | None = None
    selected_ids: str = ""  # comma-separated choice ids
    is_correct: bool | None = None  # None until answered
    answered_at: datetime | None = None

    attempt: Attempt = Relationship(back_populates="items")

    @property
    def is_answered(self) -> bool:
        return self.is_correct is not None

    @property
    def selected(self) -> set[int]:
        return set(_ids(self.selected_ids))
