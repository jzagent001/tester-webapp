from sqlmodel import select

from app.models import Attempt, Bank, Module, Question
from app.topics import weak_points


def test_home_empty(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Load the example bank" in r.text


def test_footer_links_to_source(client, monkeypatch):
    from app import config

    assert 'href="https://github.com/jzagent001/tester-webapp">Source code' in client.get("/").text
    monkeypatch.setattr(config, "SOURCE_URL", "https://example.com/fork")
    assert 'href="https://example.com/fork">Source code' in client.get("/").text


def test_create_bank(client, session):
    r = client.post("/banks", data={"name": "CCNA"}, follow_redirects=False)
    assert r.status_code == 303
    bank = session.exec(select(Bank)).one()
    assert r.headers["location"] == f"/banks/{bank.id}/topics"


def test_bank_names_unique(client, bank):
    r = client.post("/banks", data={"name": "test BANK"})
    assert r.status_code == 422
    assert "already have a bank" in r.text


def test_settings(client, session, bank):
    r = client.post(
        f"/banks/{bank.id}/settings",
        data={"name": "Renamed", "description": "d", "quiz_length": "25", "pass_mark": "70"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    session.refresh(bank)
    assert (bank.name, bank.quiz_length, bank.pass_mark) == ("Renamed", 25, 70)


def test_settings_validation(client, bank):
    r = client.post(
        f"/banks/{bank.id}/settings",
        data={"name": "", "quiz_length": "0", "pass_mark": "150"},
    )
    assert r.status_code == 422
    assert "Name is required." in r.text and "Pass mark" in r.text


def test_delete_bank_removes_everything(client, session, bank, topics, make_question):
    _, loss, _ = topics
    make_question(point=loss)
    client.post(f"/banks/{bank.id}/quiz", data={"count": 1})
    r = client.post(f"/banks/{bank.id}/delete", follow_redirects=False)
    assert r.status_code == 303
    session.expire_all()
    for model in (Bank, Module, Question, Attempt):
        assert session.exec(select(model)).all() == []


def test_dashboard_weak_points(client, session, user, bank, topics, make_question):
    _, loss, dispersion = topics
    for i in range(3):
        make_question(f"loss {i}", point=loss)
        make_question(f"disp {i}", point=dispersion)
    r = client.post(f"/banks/{bank.id}/quiz", data={"count": 6}, follow_redirects=False)
    attempt_id = int(r.headers["location"].split("/")[2])
    attempt = session.get(Attempt, attempt_id)
    for item in attempt.items:
        q = session.get(Question, item.question_id)
        right = q.knowledge_point_id == loss.id
        pick = [c.id for c in q.choices if c.is_correct == right][:1] if not right else list(q.correct_ids)
        client.post(f"/quiz/{attempt_id}/q/{item.position}", data={"choice": pick})

    session.expire_all()
    rows = weak_points(session, session.get(Bank, bank.id), user)
    assert [(label, t.correct, t.answered) for label, t in rows] == [
        ("Optics › Dispersion", 0, 3),
        ("Optics › Loss", 3, 3),
    ]
    r = client.get(f"/banks/{bank.id}")
    assert "Optics › Dispersion" in r.text and "0/3 (0%)" in r.text
