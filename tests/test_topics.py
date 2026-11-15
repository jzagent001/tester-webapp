from app.models import Bank, KnowledgePoint, Module, Question


def test_create_module_and_point(client, session, bank):
    r = client.post(f"/banks/{bank.id}/modules", data={"name": " Optics "}, follow_redirects=False)
    assert r.status_code == 303
    session.refresh(bank)
    (module,) = bank.modules
    assert module.name == "Optics"
    client.post(f"/banks/{bank.id}/modules/{module.id}/points", data={"name": "Loss", "description": "dB/km"})
    session.refresh(module)
    assert [(p.name, p.description) for p in module.points] == [("Loss", "dB/km")]


def test_duplicate_names_rejected_case_insensitively(client, bank, topics):
    module, _, _ = topics
    r = client.post(f"/banks/{bank.id}/modules", data={"name": "OPTICS"})
    assert r.status_code == 422
    assert "already a module" in r.text
    r = client.post(f"/banks/{bank.id}/modules/{module.id}/points", data={"name": "loss"})
    assert r.status_code == 422


def test_rename_point(client, session, bank, topics):
    _, loss, _ = topics
    client.post(f"/banks/{bank.id}/points/{loss.id}", data={"name": "Attenuation", "description": ""})
    session.refresh(loss)
    assert loss.name == "Attenuation"


def test_move_point(client, session, bank, topics):
    module, _, dispersion = topics
    client.post(f"/banks/{bank.id}/points/{dispersion.id}/move", data={"direction": "-1"})
    session.refresh(module)
    assert [p.name for p in module.points] == ["Dispersion", "Loss"]


def test_delete_point_makes_questions_module_general(client, session, bank, topics, make_question):
    module, loss, _ = topics
    q = make_question(point=loss)
    client.post(f"/banks/{bank.id}/points/{loss.id}/delete")
    session.expire_all()
    q = session.get(Question, q.id)
    assert (q.module_id, q.knowledge_point_id) == (module.id, None)


def test_delete_module_makes_questions_general(client, session, bank, topics, make_question):
    module, loss, _ = topics
    q1 = make_question("Q1", point=loss)
    q2 = make_question("Q2", module=module)
    client.post(f"/banks/{bank.id}/modules/{module.id}/delete")
    session.expire_all()
    assert session.get(Module, module.id) is None
    assert session.get(KnowledgePoint, loss.id) is None
    for qid in (q1.id, q2.id):
        q = session.get(Question, qid)
        assert (q.module_id, q.knowledge_point_id) == (None, None)


def test_topics_of_another_bank_are_404(client, session, topics):
    other = Bank(name="Other")
    session.add(other)
    session.commit()
    module, loss, _ = topics
    assert client.post(f"/banks/{other.id}/modules/{module.id}", data={"name": "x"}).status_code == 404
    assert client.post(f"/banks/{other.id}/points/{loss.id}/delete").status_code == 404
