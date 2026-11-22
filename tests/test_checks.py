from app.checks import answer_length_bias
from app.crud import load_example_bank

LONG = "This is the correct answer with all of its careful qualifiers"
SHORT = ("Wrong one", "Wrong two", "Wrong three")


def biased(make_question, n, start=0):
    for i in range(start, start + n):
        make_question(text=f"Biased {i}?", choices=[(LONG, True)] + [(w, False) for w in SHORT])


def balanced(make_question, n, start=0):
    for i in range(start, start + n):
        make_question(
            text=f"Balanced {i}?",
            choices=[("Short right", True), ("A longer wrong answer here", False), ("Wrong", False), ("No", False)],
        )


def test_no_warning_for_balanced_bank(session, bank, make_question):
    biased(make_question, 3)
    balanced(make_question, 9)  # 3 of 12 = 25%
    assert answer_length_bias(session, bank.id) is None


def test_warning_lists_clearly_longer_questions(session, bank, make_question):
    biased(make_question, 6)
    balanced(make_question, 6)  # 6 of 12 = 50%
    result = answer_length_bias(session, bank.id)
    assert (result.checked, result.longest, result.percent) == (12, 6, 50)
    assert len(result.clear) == 6


def test_small_banks_are_not_judged(session, bank, make_question):
    biased(make_question, 9)
    assert answer_length_bias(session, bank.id) is None


def test_multiple_answer_and_two_choice_questions_are_skipped(session, bank, make_question):
    biased(make_question, 9)
    make_question(text="Multi?", choices=[(LONG, True), ("Also right", True), ("Wrong", False)])
    make_question(text="True or false?", choices=[(LONG, True), ("False", False)])
    assert answer_length_bias(session, bank.id) is None  # still only 9 checkable


def test_dashboard_shows_warning_with_edit_links(client, bank, make_question):
    biased(make_question, 10)
    page = client.get(f"/banks/{bank.id}").text
    assert "The correct answer is often the longest choice" in page
    assert f"/banks/{bank.id}/questions/" in page and "/edit" in page


def test_dashboard_quiet_for_balanced_bank(client, bank, make_question):
    balanced(make_question, 10)
    assert "often the longest choice" not in client.get(f"/banks/{bank.id}").text


def test_import_result_warns(client, bank):
    rows = "".join(f"Q{i}?,{LONG},Wrong a,Wrong b,Wrong c,A\n" for i in range(10))
    csv = "question,A,B,C,D,correct\n" + rows
    r = client.post("/import", data={"bank_id": str(bank.id)}, files={"file": ("q.csv", csv)}, headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "often the longest choice" in r.text


def test_example_bank_passes(session, user):
    bank, _ = load_example_bank(session, user)
    assert answer_length_bias(session, bank.id) is None
