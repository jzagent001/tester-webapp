from app.models import Attempt, Question
from app.topics import breakdown
from tests.conftest import HTMX


def _start(client, bank, **data):
    r = client.post(f"/banks/{bank.id}/quiz", data={"count": 10, **data}, follow_redirects=False)
    assert r.status_code == 303, r.text
    attempt_id = int(r.headers["location"].split("/")[2])
    return attempt_id


def test_scope_limits_questions(client, session, bank, topics, make_question):
    _, loss, dispersion = topics
    a = make_question("A", point=loss)
    make_question("B", point=dispersion)
    c = make_question("C")
    attempt_id = _start(client, bank, scope=[f"k:{loss.id}", "none"])
    attempt = session.get(Attempt, attempt_id)
    assert {i.question_id for i in attempt.items} == {a.id, c.id}
    assert attempt.scope == "Optics › Loss; General"


def test_whole_module_scope_label(client, session, bank, topics, make_question):
    module, loss, dispersion = topics
    make_question("A", point=loss)
    attempt_id = _start(client, bank, scope=[f"k:{loss.id}", f"k:{dispersion.id}", f"mg:{module.id}"])
    assert session.get(Attempt, attempt_id).scope == "Optics"


def test_no_scope_means_everything(client, session, bank, topics, make_question):
    _, loss, _ = topics
    make_question("A", point=loss)
    make_question("B")
    attempt = session.get(Attempt, _start(client, bank))
    assert attempt.total == 2 and attempt.scope == ""


def test_empty_selection_is_an_error(client, bank, topics, make_question):
    _, _, dispersion = topics
    make_question("A")
    r = client.post(f"/banks/{bank.id}/quiz", data={"count": 5, "scope": [f"k:{dispersion.id}"]})
    assert r.status_code == 422
    assert "no questions in that selection" in r.text


def test_item_snapshots_classification(client, session, bank, topics, make_question):
    module, loss, _ = topics
    q = make_question(point=loss)
    attempt = session.get(Attempt, _start(client, bank))
    (item,) = attempt.items
    assert (item.question_id, item.module_id, item.knowledge_point_id) == (q.id, module.id, loss.id)


def test_submit_correct_and_first_answer_counts(client, session, bank, make_question):
    q = make_question()
    attempt_id = _start(client, bank)
    right = [c.id for c in q.choices if c.is_correct]
    wrong = [c.id for c in q.choices if not c.is_correct][:1]
    r = client.post(f"/quiz/{attempt_id}/q/1", data={"choice": right}, headers=HTMX)
    assert "Correct!" in r.text
    r = client.post(f"/quiz/{attempt_id}/q/1", data={"choice": wrong}, headers=HTMX)
    assert "Correct!" in r.text
    assert session.get(Attempt, attempt_id).score == 1


def test_submit_without_choice(client, bank, make_question):
    make_question()
    attempt_id = _start(client, bank)
    r = client.post(f"/quiz/{attempt_id}/q/1", headers=HTMX)
    assert r.status_code == 422
    assert "Select at least one answer." in r.text


def test_multi_answer_needs_all(client, session, bank, make_question):
    q = make_question(choices=(("a", True), ("b", True), ("c", False)))
    attempt_id = _start(client, bank)
    first = [c.id for c in q.choices if c.is_correct][:1]
    r = client.post(f"/quiz/{attempt_id}/q/1", data={"choice": first}, headers=HTMX)
    assert "Incorrect." in r.text


def test_results_breakdown(client, session, bank, topics, make_question):
    _, loss, dispersion = topics
    for i in range(2):
        make_question(f"loss {i}", point=loss)
    make_question("disp", point=dispersion)
    make_question("general")
    attempt_id = _start(client, bank)
    attempt = session.get(Attempt, attempt_id)
    for item in attempt.items:
        q = session.get(Question, item.question_id)
        if q.knowledge_point_id == loss.id:
            client.post(f"/quiz/{attempt_id}/q/{item.position}", data={"choice": list(q.correct_ids)})
    session.refresh(attempt)
    rows = breakdown(bank, attempt.items)
    assert [(r.name, r.tally.correct, r.tally.total) for r in rows] == [("Optics", 2, 3), ("General", 0, 1)]
    assert [(name, t.correct, t.total) for name, t in rows[0].points] == [("Loss", 2, 2), ("Dispersion", 0, 1)]

    r = client.get(f"/quiz/{attempt_id}/results")
    assert r.status_code == 200
    assert "2 / 4 (50%)" in r.text
    assert "By topic" in r.text


def test_pass_mark(client, session, bank, make_question):
    bank.pass_mark = 50
    session.add(bank)
    session.commit()
    q = make_question()
    attempt_id = _start(client, bank)
    client.post(f"/quiz/{attempt_id}/q/1", data={"choice": list(q.correct_ids)})
    assert "Pass" in client.get(f"/quiz/{attempt_id}/results").text


def test_deleted_question_mid_test(client, session, bank, make_question):
    q = make_question()
    attempt_id = _start(client, bank)
    session.delete(q)
    session.commit()
    assert "has been deleted" in client.get(f"/quiz/{attempt_id}/q/1").text
    assert "was deleted" in client.get(f"/quiz/{attempt_id}/results").text


def test_out_of_range_step(client, bank, make_question):
    make_question()
    attempt_id = _start(client, bank)
    assert client.get(f"/quiz/{attempt_id}/q/2").status_code == 404
