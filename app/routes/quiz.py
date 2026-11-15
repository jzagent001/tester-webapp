import random
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.crud import classification_counts
from app.db import SessionDep
from app.models import Attempt, AttemptItem, Bank, Choice, Question, utcnow
from app.templating import get_bank, is_htmx, templates
from app.topics import breakdown, scope_label, tokens_clause, topic_tree

router = APIRouter(tags=["quiz"])


def _setup_page(
    request: Request,
    session: Session,
    bank: Bank,
    error: str | None = None,
    selected: list[str] | None = None,
    status_code: int = 200,
):
    tree = topic_tree(bank, classification_counts(session, bank.id))
    total = sum(g.count for g in tree)
    return templates.TemplateResponse(
        request,
        "quiz/setup.html",
        {
            "bank": bank,
            "tree": tree,
            "total": total,
            "default_count": min(bank.quiz_length, total) or bank.quiz_length,
            "selected": set(selected or []),
            "error": error,
        },
        status_code=status_code,
    )


def _get_attempt(session: Session, attempt_id: int) -> Attempt:
    attempt = session.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return attempt


def _load_step(
    session: Session, attempt_id: int, n: int
) -> tuple[Attempt, AttemptItem, Question | None]:
    attempt = _get_attempt(session, attempt_id)
    if not 1 <= n <= attempt.total:
        raise HTTPException(status_code=404, detail="No such question in this test")
    item = attempt.items[n - 1]
    question = session.get(Question, item.question_id)
    # None if the question was deleted (or moved out of the bank) after the test started.
    if question is not None and question.bank_id != attempt.bank_id:
        question = None
    return attempt, item, question


def _shuffled_choices(attempt: Attempt, question: Question) -> list[Choice]:
    """Choice order is random per test but stable across page loads."""
    choices = list(question.choices)
    random.Random(f"{attempt.id}:{question.id}").shuffle(choices)
    return choices


def _card_context(
    attempt: Attempt, n: int, item: AttemptItem, question: Question | None, error: str | None = None
):
    total = attempt.total
    return {
        "bank": attempt.bank,
        "attempt": attempt,
        "n": n,
        "total": total,
        "item": item,
        "question": question,
        "choices": _shuffled_choices(attempt, question) if question else [],
        "next_url": (
            f"/quiz/{attempt.id}/q/{n + 1}" if n < total else f"/quiz/{attempt.id}/results"
        ),
        "error": error,
    }


@router.get("/banks/{bank_id}/quiz")
def quiz_setup(request: Request, session: SessionDep, bank_id: int):
    return _setup_page(request, session, get_bank(session, bank_id))


@router.post("/banks/{bank_id}/quiz")
def start_quiz(
    request: Request,
    session: SessionDep,
    bank_id: int,
    scope: Annotated[list[str], Form()] = [],
    count: Annotated[int, Form(ge=1)] = 1,
):
    bank = get_bank(session, bank_id)
    stmt = select(Question.id, Question.module_id, Question.knowledge_point_id).where(
        Question.bank_id == bank.id
    )
    if scope:
        stmt = stmt.where(tokens_clause(scope))
    rows = session.exec(stmt).all()
    if not rows:
        return _setup_page(
            request,
            session,
            bank,
            error="There are no questions in that selection yet.",
            selected=scope,
            status_code=422,
        )
    chosen = random.sample(list(rows), min(count, len(rows)))
    attempt = Attempt(bank_id=bank.id, scope=scope_label(bank, scope))
    attempt.items = [
        AttemptItem(position=i, question_id=qid, module_id=mid, knowledge_point_id=kid)
        for i, (qid, mid, kid) in enumerate(chosen, start=1)
    ]
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return RedirectResponse(f"/quiz/{attempt.id}/q/1", status_code=303)


@router.get("/quiz/{attempt_id}/q/{n}")
def show_question(request: Request, session: SessionDep, attempt_id: int, n: int):
    attempt, item, question = _load_step(session, attempt_id, n)
    return templates.TemplateResponse(
        request, "quiz/question.html", _card_context(attempt, n, item, question)
    )


@router.post("/quiz/{attempt_id}/q/{n}")
def submit_answer(
    request: Request,
    session: SessionDep,
    attempt_id: int,
    n: int,
    choice: Annotated[list[int], Form()] = [],
):
    attempt, item, question = _load_step(session, attempt_id, n)
    if question is None:
        raise HTTPException(status_code=404, detail="This question has been deleted")
    template = "quiz/_card.html" if is_htmx(request) else "quiz/question.html"

    # The first answer counts; resubmitting just shows the feedback again.
    if not item.is_answered:
        selected = set(choice) & {c.id for c in question.choices}
        if not selected:
            return templates.TemplateResponse(
                request,
                template,
                _card_context(attempt, n, item, question, error="Select at least one answer."),
                status_code=422,
            )
        item.selected_ids = ",".join(map(str, sorted(selected)))
        item.is_correct = selected == question.correct_ids
        item.answered_at = utcnow()
        session.add(item)
        session.commit()
        session.refresh(item)

    if not is_htmx(request):
        return RedirectResponse(f"/quiz/{attempt_id}/q/{n}", status_code=303)
    return templates.TemplateResponse(request, template, _card_context(attempt, n, item, question))


@router.get("/quiz/{attempt_id}/results")
def results(request: Request, session: SessionDep, attempt_id: int):
    attempt = _get_attempt(session, attempt_id)
    if attempt.finished_at is None:
        attempt.finished_at = utcnow()
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

    review = []
    for item in attempt.items:
        if item.is_correct:
            continue
        question = session.get(Question, item.question_id)
        if question is not None and question.bank_id != attempt.bank_id:
            question = None
        review.append(
            {
                "n": item.position,
                "item": item,
                "question": question,
                "choices": _shuffled_choices(attempt, question) if question else [],
            }
        )
    total = attempt.total
    score = attempt.score
    pct = round(100 * score / total) if total else 0
    bank = attempt.bank
    return templates.TemplateResponse(
        request,
        "quiz/results.html",
        {
            "bank": bank,
            "attempt": attempt,
            "score": score,
            "total": total,
            "pct": pct,
            "passed": None if bank.pass_mark is None else pct >= bank.pass_mark,
            "answered": attempt.answered,
            "breakdown": breakdown(bank, attempt.items),
            "review": review,
        },
    )
