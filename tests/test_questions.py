from sqlmodel import select

from app.crud import add_module
from app.models import Question
from tests.conftest import HTMX, form_for


def test_create_with_knowledge_point(client, session, bank, topics):
    module, loss, _ = topics
    r = client.post(
        f"/banks/{bank.id}/questions",
        data=form_for(text="New?", module_id=module.id, point_id=loss.id),
        follow_redirects=False,
    )
    assert r.status_code == 303
    q = session.exec(select(Question)).one()
    assert (q.bank_id, q.module_id, q.knowledge_point_id) == (bank.id, module.id, loss.id)
    assert q.topic_label == "Optics › Loss"


def test_create_general_question(client, session, bank):
    client.post(f"/banks/{bank.id}/questions", data=form_for(text="General?"))
    q = session.exec(select(Question)).one()
    assert (q.module_id, q.knowledge_point_id, q.topic_label) == (None, None, "General")


def test_point_from_another_module_rejected(client, session, bank, topics):
    _, loss, _ = topics
    other_module = add_module(session, bank, "Other")
    session.commit()
    r = client.post(
        f"/banks/{bank.id}/questions", data=form_for(module_id=other_module.id, point_id=loss.id)
    )
    assert r.status_code == 422
    assert "does not belong to the chosen module" in r.text


def test_module_from_another_bank_rejected(client, session, topics, make_bank):
    module, _, _ = topics
    other = make_bank("Other")
    r = client.post(f"/banks/{other.id}/questions", data=form_for(module_id=module.id))
    assert r.status_code == 422
    assert "does not belong to this bank" in r.text


def test_validation_errors_keep_input(client, bank):
    r = client.post(f"/banks/{bank.id}/questions", data=form_for(text="Keep me", choices=(("a", False), ("b", False))))
    assert r.status_code == 422
    assert "Mark at least one choice as correct." in r.text
    assert "Keep me" in r.text


def test_edit_changes_classification(client, session, bank, topics, make_question):
    module, loss, dispersion = topics
    q = make_question(point=loss)
    client.post(
        f"/banks/{bank.id}/questions/{q.id}",
        data=form_for(text="Edited", module_id=module.id, point_id=dispersion.id),
    )
    session.refresh(q)
    assert (q.text, q.knowledge_point_id) == ("Edited", dispersion.id)


def test_edit_form_preselects_topic(client, bank, topics, make_question):
    _, loss, _ = topics
    q = make_question(point=loss)
    r = client.get(f"/banks/{bank.id}/questions/{q.id}/edit")
    assert f'<option value="{loss.id}" selected>Loss</option>' in r.text


def test_point_options_fragment(client, bank, topics):
    module, _, _ = topics
    r = client.get(f"/banks/{bank.id}/questions/point-options", params={"module_id": module.id}, headers=HTMX)
    assert "Loss" in r.text and "Dispersion" in r.text
    r = client.get(f"/banks/{bank.id}/questions/point-options", params={"module_id": ""}, headers=HTMX)
    assert "Choose a module first" in r.text


def test_filter_by_topic_tokens(client, bank, topics, make_question):
    module, loss, dispersion = topics
    make_question("About loss", point=loss)
    make_question("About dispersion", point=dispersion)
    make_question("Module general", module=module)
    make_question("Bank general")

    def texts(topic):
        r = client.get(
            f"/banks/{bank.id}/questions",
            params={"topic": topic},
            headers={**HTMX, "HX-Target": "question-rows"},
        )
        return {t for t in ("About loss", "About dispersion", "Module general", "Bank general") if t in r.text}

    assert texts(f"k:{loss.id}") == {"About loss"}
    assert texts(f"mg:{module.id}") == {"Module general"}
    assert texts(f"m:{module.id}") == {"About loss", "About dispersion", "Module general"}
    assert texts("none") == {"Bank general"}
    assert len(texts("")) == 4


def test_questions_of_another_bank_are_404(client, session, make_question, make_bank):
    q = make_question()
    other = make_bank("Other")
    assert client.get(f"/banks/{other.id}/questions/{q.id}/edit").status_code == 404
    assert client.delete(f"/banks/{other.id}/questions/{q.id}").status_code == 404


def test_delete(client, session, bank, make_question):
    q = make_question()
    r = client.delete(f"/banks/{bank.id}/questions/{q.id}", headers=HTMX)
    assert r.status_code == 200 and r.text == ""
    assert session.get(Question, q.id) is None
