from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, col, select

from app.auth import CurrentUser
from app.crud import apply_data, check_classification, classification_counts
from app.csv_io import QuestionData, validate
from app.db import SessionDep
from app.models import Bank, KnowledgePoint, Module, Question
from app.templating import get_bank, is_htmx, optional_int, templates
from app.topics import token_clause, topic_tree

router = APIRouter(prefix="/banks/{bank_id}/questions", tags=["questions"])


def _new_key() -> str:
    return uuid4().hex[:10]


def _blank_choices(n: int) -> list[dict]:
    return [{"key": _new_key(), "text": "", "correct": False} for _ in range(n)]


def _get_question(session: Session, bank: Bank, question_id: int) -> Question:
    question = session.get(Question, question_id)
    if question is None or question.bank_id != bank.id:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


async def _read_form(request: Request) -> tuple[QuestionData, dict, list[dict]]:
    """Parse the question form. Choices arrive as choice_text_<key> / choice_correct_<key>."""
    form = await request.form()
    rows: dict[str, dict] = {}
    for name, value in form.multi_items():
        for prefix in ("choice_text_", "choice_correct_"):
            if name.startswith(prefix):
                row = rows.setdefault(name.removeprefix(prefix), {"text": "", "correct": False})
                if prefix == "choice_text_":
                    row["text"] = str(value).strip()
                else:
                    row["correct"] = True
    raw_choices = [{"key": key, **row} for key, row in rows.items()]
    values = {
        name: str(form.get(name, "")).strip()
        for name in ("text", "explanation", "module_id", "knowledge_point_id")
    }
    data = QuestionData(
        text=values["text"],
        explanation=values["explanation"],
        choices=[(r["text"], r["correct"]) for r in raw_choices if r["text"]],
    )
    return data, values, raw_choices


def _points_for(session: Session, module_id: int | None):
    module = session.get(Module, module_id) if module_id else None
    return module.points if module else []


def _render_form(
    request: Request,
    session: Session,
    bank: Bank,
    *,
    heading: str,
    action: str,
    values: dict,
    choices: list[dict],
    errors: list[str] | None = None,
    status_code: int = 200,
):
    module_id = optional_int(values.get("module_id"))
    return templates.TemplateResponse(
        request,
        "questions/form.html",
        {
            "bank": bank,
            "heading": heading,
            "action": action,
            "values": values,
            "choices": choices,
            "points": _points_for(session, module_id),
            "errors": errors or [],
        },
        status_code=status_code,
    )


async def _save(request: Request, session: Session, bank: Bank, question: Question | None):
    data, values, raw_choices = await _read_form(request)
    module_id = optional_int(values["module_id"])
    point_id = optional_int(values["knowledge_point_id"]) if module_id else None
    errors = validate(data) + check_classification(session, bank.id, module_id, point_id)
    if errors:
        heading = "New question" if question is None else f"Edit question #{question.id}"
        action = (
            f"/banks/{bank.id}/questions"
            if question is None
            else f"/banks/{bank.id}/questions/{question.id}"
        )
        return _render_form(
            request,
            session,
            bank,
            heading=heading,
            action=action,
            values=values,
            choices=raw_choices,
            errors=errors,
            status_code=422,
        )
    question = question or Question(bank_id=bank.id, text="")
    session.add(apply_data(question, data, module_id, point_id))
    session.commit()
    return RedirectResponse(f"/banks/{bank.id}/questions", status_code=303)


@router.get("")
def list_questions(request: Request, session: SessionDep, user: CurrentUser, bank_id: int, topic: str = "", q: str = ""):
    bank = get_bank(session, user, bank_id)
    stmt = (
        select(Question)
        .where(Question.bank_id == bank.id)
        .order_by(col(Question.module_id).is_(None), Question.module_id, col(Question.id))
    )
    if topic and (clause := token_clause(topic)) is not None:
        stmt = stmt.where(clause)
    if q:
        stmt = stmt.where(col(Question.text).icontains(q))
    context = {
        "bank": bank,
        "questions": session.exec(stmt).all(),
        "tree": topic_tree(bank, classification_counts(session, bank.id)),
        "topic": topic,
        "q": q,
    }
    if is_htmx(request) and request.headers.get("HX-Target") == "question-rows":
        return templates.TemplateResponse(request, "questions/_rows.html", context)
    return templates.TemplateResponse(request, "questions/list.html", context)


@router.get("/new")
def new_question(request: Request, session: SessionDep, user: CurrentUser, bank_id: int, topic: str = ""):
    bank = get_bank(session, user, bank_id)
    # Pre-select the topic the list was filtered by, if any.
    values = {"text": "", "explanation": "", "module_id": "", "knowledge_point_id": ""}
    kind, _, raw = topic.partition(":")
    if kind in ("m", "mg") and raw.isdigit():
        values["module_id"] = raw
    elif kind == "k" and raw.isdigit():
        point = session.get(KnowledgePoint, int(raw))
        if point is not None and point.module.bank_id == bank.id:
            values["module_id"], values["knowledge_point_id"] = str(point.module_id), raw
    return _render_form(
        request,
        session,
        bank,
        heading="New question",
        action=f"/banks/{bank.id}/questions",
        values=values,
        choices=_blank_choices(4),
    )


@router.get("/choice-field")
def choice_field(request: Request, bank_id: int):
    """HTMX fragment: one more empty answer-choice row."""
    return templates.TemplateResponse(
        request, "questions/_choice_field.html", {"c": _blank_choices(1)[0]}
    )


@router.get("/point-options")
def point_options(request: Request, session: SessionDep, user: CurrentUser, bank_id: int, module_id: str = ""):
    """HTMX fragment: the knowledge-point <option>s for the chosen module."""
    bank = get_bank(session, user, bank_id)
    mid = optional_int(module_id)
    points = [p for p in _points_for(session, mid) if p.module.bank_id == bank.id]
    return templates.TemplateResponse(
        request,
        "questions/_point_options.html",
        {"points": points, "values": {"module_id": module_id, "knowledge_point_id": ""}},
    )


@router.post("")
async def create_question(request: Request, session: SessionDep, user: CurrentUser, bank_id: int):
    return await _save(request, session, get_bank(session, user, bank_id), None)


@router.get("/{question_id}/edit")
def edit_question(request: Request, session: SessionDep, user: CurrentUser, bank_id: int, question_id: int):
    bank = get_bank(session, user, bank_id)
    question = _get_question(session, bank, question_id)
    return _render_form(
        request,
        session,
        bank,
        heading=f"Edit question #{question.id}",
        action=f"/banks/{bank.id}/questions/{question.id}",
        values={
            "text": question.text,
            "explanation": question.explanation,
            "module_id": str(question.module_id or ""),
            "knowledge_point_id": str(question.knowledge_point_id or ""),
        },
        choices=[
            {"key": _new_key(), "text": c.text, "correct": c.is_correct} for c in question.choices
        ],
    )


@router.post("/{question_id}")
async def update_question(request: Request, session: SessionDep, user: CurrentUser, bank_id: int, question_id: int):
    bank = get_bank(session, user, bank_id)
    return await _save(request, session, bank, _get_question(session, bank, question_id))


@router.delete("/{question_id}", response_class=HTMLResponse)
def delete_question(session: SessionDep, user: CurrentUser, bank_id: int, question_id: int):
    bank = get_bank(session, user, bank_id)
    session.delete(_get_question(session, bank, question_id))
    session.commit()
    # Empty body: HTMX swaps the table row out with nothing.
    return HTMLResponse("")
