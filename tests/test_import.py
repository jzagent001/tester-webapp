import io

from sqlmodel import select

from app.config import BASE_DIR
from app.crud import import_csv_text, load_example_bank, question_count
from app.models import Bank, Question

CSV = (
    "module,knowledge_point,question,A,B,correct\n"
    "Optics,Loss,Q1,x,y,A\n"
    "optics,LOSS,Q2,x,y,B\n"  # same module/point, different case
    "Optics,,Q3,x,y,A\n"
    ",,Q4,x,y,A\n"
)


def test_import_creates_topics_once(session, bank):
    result = import_csv_text(session, bank, CSV)
    assert (result.imported, result.errors) == (4, [])
    assert result.new_modules == ["Optics"]
    assert result.new_points == ["Optics › Loss"]
    session.refresh(bank)
    (module,) = bank.modules
    (point,) = module.points
    labels = [q.topic_label for q in session.exec(select(Question).order_by(Question.id))]
    assert labels == ["Optics › Loss", "Optics › Loss", "Optics › General", "General"]
    assert point.name == "Loss"


def test_import_reuses_existing_topics(session, bank, topics):
    result = import_csv_text(session, bank, CSV)
    assert result.new_modules == [] and result.new_points == []


def test_duplicates_are_scoped_to_the_bank(session, bank, make_bank):
    other = make_bank("Other")
    import_csv_text(session, bank, CSV)
    again = import_csv_text(session, bank, CSV, skip_duplicates=True)
    assert (again.imported, again.skipped) == (0, 4)
    elsewhere = import_csv_text(session, other, CSV, skip_duplicates=True)
    assert elsewhere.imported == 4


def test_example_bank_loads_once(session, user):
    bank, result = load_example_bank(session, user)
    assert result.errors == []
    assert result.imported == 100
    assert len(bank.modules) == 6
    _, again = load_example_bank(session, user)
    assert (again.imported, again.skipped) == (0, 100)
    assert len(session.exec(select(Bank)).all()) == 1


def _upload(client, data, content=CSV.encode()):
    return client.post("/import", data=data, files={"file": ("q.csv", io.BytesIO(content), "text/csv")})


def test_upload_into_new_bank(client, session):
    r = _upload(client, {"new_bank": "Fresh", "skip_duplicates": "true"})
    assert r.status_code == 200
    assert "Imported 4 questions" in r.text
    bank = session.exec(select(Bank).where(Bank.name == "Fresh")).one()
    assert question_count(session, bank.id) == 4


def test_upload_into_existing_bank(client, session, bank):
    r = _upload(client, {"bank_id": str(bank.id)})
    assert "Imported 4" in r.text
    assert question_count(session, bank.id) == 4


def test_upload_needs_a_target(client):
    r = _upload(client, {})
    assert r.status_code == 422
    assert "Choose a bank" in r.text


def test_upload_rejects_non_utf8(client, bank):
    r = _upload(client, {"bank_id": str(bank.id)}, content="é".encode("latin-1"))
    assert r.status_code == 422
    assert "not UTF-8" in r.text


def test_export_is_per_bank(client, session, bank, make_question, make_bank):
    other = make_bank("Other")
    make_question("Mine")
    make_question("Theirs", target=other)
    r = client.get(f"/banks/{bank.id}/export.csv")
    assert "Mine" in r.text and "Theirs" not in r.text
    assert 'filename="Test_bank.csv"' in r.headers["content-disposition"]


def test_writing_kit_zip(client):
    import zipfile

    r = client.get("/question-writing-kit.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    names = set(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
    folder = "question writing instructions"
    expected = {f"{folder}/{p.name}" for p in (BASE_DIR / folder).iterdir() if p.is_file()}
    assert names == expected
    assert f"{folder}/QUESTION_WRITING_GUIDE.md" in names
    assert f"{folder}/sample_question_bank.csv" in names


def test_writing_kit_linked_from_home_and_import(client):
    assert "/question-writing-kit.zip" in client.get("/").text
    assert "/question-writing-kit.zip" in client.get("/import").text
