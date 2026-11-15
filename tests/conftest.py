import os

# Must be set before app.db is imported so the lifespan never touches app.db on disk.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTH_MODE"] = "single"
os.environ["SINGLE_USER_EMAIL"] = "alice@example.com"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app import config  # noqa: E402
from app.auth import get_or_create_user  # noqa: E402
from app.crud import add_module, add_point, apply_data  # noqa: E402
from app.csv_io import QuestionData  # noqa: E402
from app.db import create_db_and_tables, get_session, make_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Bank, KnowledgePoint, Module, Question, User  # noqa: E402

HTMX = {"HX-Request": "true"}


@pytest.fixture
def session():
    engine = make_engine("sqlite://")
    create_db_and_tables(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture(autouse=True)
def act_as(monkeypatch):
    """Requests are made as alice by default; `act_as("bob@example.com")` switches user.

    Uses the real single-user sign-in path (app.auth), just with a different email.
    """
    monkeypatch.setattr(config, "AUTH_MODE", "single")

    def _act_as(email: str) -> None:
        monkeypatch.setattr(config, "SINGLE_USER_EMAIL", email)

    _act_as("alice@example.com")
    return _act_as


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(session) -> User:
    return get_or_create_user(session, "alice@example.com")


@pytest.fixture
def other_user(session) -> User:
    return get_or_create_user(session, "bob@example.com")


@pytest.fixture
def make_bank(session, user):
    def _make(name="Test bank", owner: User | None = None, **fields) -> Bank:
        bank = Bank(owner_id=(owner or user).id, name=name, **{"quiz_length": 10, **fields})
        session.add(bank)
        session.commit()
        session.refresh(bank)
        return bank

    return _make


@pytest.fixture
def bank(make_bank) -> Bank:
    return make_bank()


@pytest.fixture
def topics(session, bank) -> tuple[Module, KnowledgePoint, KnowledgePoint]:
    """One module "Optics" with knowledge points "Loss" and "Dispersion"."""
    module = add_module(session, bank, "Optics")
    loss = add_point(session, module, "Loss")
    dispersion = add_point(session, module, "Dispersion")
    session.commit()
    return module, loss, dispersion


@pytest.fixture
def make_question(session, bank):
    def _make(
        text="What is 0 dBm?",
        module: Module | None = None,
        point: KnowledgePoint | None = None,
        choices=(("1 mW", True), ("0 mW", False), ("10 mW", False)),
        explanation="dBm is relative to 1 mW.",
        target: Bank | None = None,
    ) -> Question:
        target = target or bank
        module_id = point.module_id if point else (module.id if module else None)
        question = apply_data(
            Question(bank_id=target.id, text=""),
            QuestionData(text=text, explanation=explanation, choices=list(choices)),
            module_id,
            point.id if point else None,
        )
        session.add(question)
        session.commit()
        session.refresh(question)
        return question

    return _make


def form_for(text="Q?", explanation="", choices=(("a", True), ("b", False)), module_id="", point_id="") -> dict:
    """Build the question-form payload the browser would send."""
    data = {
        "text": text,
        "explanation": explanation,
        "module_id": str(module_id),
        "knowledge_point_id": str(point_id),
    }
    for i, (choice_text, correct) in enumerate(choices):
        if correct:
            data[f"choice_correct_k{i}"] = "on"
        data[f"choice_text_k{i}"] = choice_text
    return data
