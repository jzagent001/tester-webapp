"""One user can never see or change another user's banks or test results."""

import io

import pytest
from sqlmodel import select

from app.models import Attempt, Bank, Question
from tests.conftest import HTMX, form_for


@pytest.fixture
def alices(session, client, bank, topics, make_question):
    """Alice's bank with one module/point/question and a test she started."""
    module, loss, _ = topics
    question = make_question(point=loss)
    r = client.post(f"/banks/{bank.id}/quiz", data={"count": 1}, follow_redirects=False)
    attempt_id = int(r.headers["location"].split("/")[2])
    return {"bank": bank, "module": module, "point": loss, "question": question, "attempt": attempt_id}


def _routes(a):
    b, m, k, q, t = a["bank"].id, a["module"].id, a["point"].id, a["question"].id, a["attempt"]
    return [
        ("get", f"/banks/{b}", None),
        ("get", f"/banks/{b}/settings", None),
        ("post", f"/banks/{b}/settings", {"name": "Mine now", "quiz_length": "5"}),
        ("post", f"/banks/{b}/delete", None),
        ("get", f"/banks/{b}/topics", None),
        ("post", f"/banks/{b}/modules", {"name": "Injected"}),
        ("post", f"/banks/{b}/modules/{m}", {"name": "Renamed"}),
        ("post", f"/banks/{b}/modules/{m}/move", {"direction": "1"}),
        ("post", f"/banks/{b}/modules/{m}/delete", None),
        ("post", f"/banks/{b}/modules/{m}/points", {"name": "Injected"}),
        ("post", f"/banks/{b}/points/{k}", {"name": "Renamed"}),
        ("post", f"/banks/{b}/points/{k}/move", {"direction": "1"}),
        ("post", f"/banks/{b}/points/{k}/delete", None),
        ("get", f"/banks/{b}/questions", None),
        ("get", f"/banks/{b}/questions/new", None),
        ("get", f"/banks/{b}/questions/point-options?module_id={m}", None),
        ("post", f"/banks/{b}/questions", form_for()),
        ("get", f"/banks/{b}/questions/{q}/edit", None),
        ("post", f"/banks/{b}/questions/{q}", form_for(text="Hijacked")),
        ("delete", f"/banks/{b}/questions/{q}", None),
        ("get", f"/banks/{b}/quiz", None),
        ("post", f"/banks/{b}/quiz", {"count": "1"}),
        ("get", f"/banks/{b}/export.csv", None),
        ("get", f"/quiz/{t}/q/1", None),
        ("post", f"/quiz/{t}/q/1", {"choice": [str(c.id) for c in a["question"].choices]}),
        ("get", f"/quiz/{t}/results", None),
    ]


def test_every_route_is_404_for_another_user(client, session, alices, act_as):
    act_as("bob@example.com")
    for method, path, data in _routes(alices):
        kwargs = {"data": data} if data is not None and method != "delete" else {}
        r = getattr(client, method)(path, headers=HTMX, follow_redirects=False, **kwargs)
        assert r.status_code == 404, f"{method.upper()} {path} -> {r.status_code}"

    # ...and nothing of Alice's changed.
    session.expire_all()
    bank = session.get(Bank, alices["bank"].id)
    assert bank.name == "Test bank"
    assert [m.name for m in bank.modules] == ["Optics"]
    assert [p.name for p in bank.modules[0].points] == ["Loss", "Dispersion"]
    assert session.get(Question, alices["question"].id).text == "What is 0 dBm?"
    assert session.get(Attempt, alices["attempt"]).items[0].is_answered is False


def test_home_and_import_only_list_own_banks(client, alices, act_as):
    act_as("bob@example.com")
    assert "Test bank" not in client.get("/").text
    assert "Test bank" not in client.get("/import").text


def test_cannot_import_into_someone_elses_bank(client, session, alices, act_as):
    act_as("bob@example.com")
    csv = b"question,A,B,correct\nInjected?,x,y,A\n"
    r = client.post(
        "/import",
        data={"bank_id": str(alices["bank"].id)},
        files={"file": ("q.csv", io.BytesIO(csv), "text/csv")},
    )
    assert r.status_code == 422
    assert session.exec(select(Question).where(Question.text == "Injected?")).first() is None


def test_bank_names_are_per_user(client, session, alices, act_as):
    act_as("bob@example.com")
    r = client.post("/banks", data={"name": "Test bank"}, follow_redirects=False)
    assert r.status_code == 303
    assert len(session.exec(select(Bank).where(Bank.name == "Test bank")).all()) == 2


def test_example_bank_is_per_user(client, session, act_as):
    client.post("/import/example")
    act_as("bob@example.com")
    client.post("/import/example")
    banks = session.exec(select(Bank)).all()
    assert len(banks) == 2 and len({b.owner_id for b in banks}) == 2


def test_dashboard_only_shows_own_attempts(client, session, alices, other_user):
    # Bob somehow has an attempt on Alice's bank (e.g. once publishing exists).
    session.add(Attempt(bank_id=alices["bank"].id, user_id=other_user.id, scope="Bob's test"))
    session.commit()
    assert "Bob's test" not in client.get(f"/banks/{alices['bank'].id}").text


def test_upload_size_limit(client, bank, monkeypatch):
    from app.routes import transfer

    monkeypatch.setattr(transfer, "MAX_UPLOAD_BYTES", 100)
    big = b"question,A,B,correct\n" + b"Q?,x,y,A\n" * 50
    r = client.post(
        "/import", data={"bank_id": str(bank.id)}, files={"file": ("q.csv", io.BytesIO(big), "text/csv")}
    )
    assert r.status_code == 422
    assert "larger than" in r.text


def test_the_same_routes_work_for_the_owner(client, alices):
    """Control for the 404 test above: the paths are real, so 404 means 'not yours'."""
    for method, path, _data in _routes(alices):
        if method == "get":
            r = client.get(path, headers=HTMX)
            assert r.status_code == 200, f"GET {path} -> {r.status_code}"
