from sqlmodel import select

from app.csv_io import parse_csv, to_csv
from app.models import Question


def test_parse_full_row():
    items, errors = parse_csv(
        "module,knowledge_point,question,A,B,C,correct,explanation\n"
        "Optics,Loss,What is it?,x,y,z,B;C,because\n"
    )
    assert errors == []
    (item,) = items
    assert (item.module, item.knowledge_point, item.text) == ("Optics", "Loss", "What is it?")
    assert item.choices == [("x", False), ("y", True), ("z", True)]


def test_module_and_point_are_optional():
    items, errors = parse_csv("question,A,B,correct\nQ?,x,y,A\n")
    assert errors == []
    assert (items[0].module, items[0].knowledge_point) == ("", "")


def test_point_without_module_is_rejected():
    items, errors = parse_csv("module,knowledge_point,question,A,B,correct\n,Loss,Q?,x,y,A\n")
    assert items == []
    assert "needs a module" in errors[0]


def test_legacy_topic_column_becomes_module():
    items, errors = parse_csv("topic,question,A,B,correct\nOld topic,Q?,x,y,A\n")
    assert errors == []
    assert items[0].module == "Old topic"


def test_header_names_are_flexible():
    items, errors = parse_csv("Module,Knowledge Point,Question,a,b,Correct\nM,K,Q?,x,y,a\n")
    assert errors == []
    assert (items[0].module, items[0].knowledge_point) == ("M", "K")


def test_missing_required_column():
    items, errors = parse_csv("module,question,A,correct\nM,Q?,x,A\n")
    assert items == []
    assert "Missing required column(s): b" in errors[0]


def test_round_trip(session, bank, topics, make_question):
    module, loss, _ = topics
    make_question("Q1", point=loss)
    make_question("Q2", module=module)
    make_question("Q3")
    questions = session.exec(select(Question).order_by(Question.id)).all()
    items, errors = parse_csv(to_csv(questions))
    assert errors == []
    assert [(i.module, i.knowledge_point, i.text) for i in items] == [
        ("Optics", "Loss", "Q1"),
        ("Optics", "", "Q2"),
        ("", "", "Q3"),
    ]


def test_writing_instructions_sample_is_valid():
    """The sample in `question writing instructions/` must stay importable."""
    from app.config import BASE_DIR

    path = BASE_DIR / "question writing instructions" / "sample_question_bank.csv"
    items, errors = parse_csv(path.read_text(encoding="utf-8"))
    assert errors == []
    levels = {(bool(i.module), bool(i.knowledge_point)) for i in items}
    assert levels == {(True, True), (True, False), (False, False)}
    assert {len(i.choices) for i in items} >= {2, 8}
    assert any(sum(c for _, c in i.choices) > 1 for i in items)
