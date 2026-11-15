from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, select

from app.auth import CurrentUser
from app.crud import classification_counts, get_bank_by_name
from app.db import SessionDep
from app.models import Attempt, Bank
from app.templating import get_bank, optional_int, templates
from app.topics import topic_tree, weak_points

router = APIRouter(prefix="/banks/{bank_id}", tags=["banks"])


@router.get("")
def dashboard(request: Request, session: SessionDep, user: CurrentUser, bank_id: int):
    bank = get_bank(session, user, bank_id)
    tree = topic_tree(bank, classification_counts(session, bank.id))
    attempts = session.exec(
        select(Attempt)
        .where(Attempt.bank_id == bank.id, Attempt.user_id == user.id)
        .order_by(col(Attempt.id).desc())
        .limit(10)
    ).all()
    return templates.TemplateResponse(
        request,
        "banks/dashboard.html",
        {
            "bank": bank,
            "tree": tree,
            "total": sum(g.count for g in tree),
            "attempts": attempts,
            "weak": weak_points(session, bank, user),
        },
    )


def _settings_page(request: Request, bank: Bank, values: dict, errors=(), status_code=200):
    return templates.TemplateResponse(
        request,
        "banks/settings.html",
        {"bank": bank, "values": values, "errors": list(errors)},
        status_code=status_code,
    )


@router.get("/settings")
def settings(request: Request, session: SessionDep, user: CurrentUser, bank_id: int):
    bank = get_bank(session, user, bank_id)
    values = {
        "name": bank.name,
        "description": bank.description,
        "quiz_length": bank.quiz_length,
        "pass_mark": "" if bank.pass_mark is None else bank.pass_mark,
    }
    return _settings_page(request, bank, values)


@router.post("/settings")
async def save_settings(request: Request, session: SessionDep, user: CurrentUser, bank_id: int):
    bank = get_bank(session, user, bank_id)
    form = await request.form()
    values = {k: str(form.get(k, "")).strip() for k in ("name", "description", "quiz_length", "pass_mark")}
    errors = []
    if not values["name"]:
        errors.append("Name is required.")
    else:
        other = get_bank_by_name(session, user.id, values["name"])
        if other is not None and other.id != bank.id:
            errors.append(f"You already have a bank called “{other.name}”.")
    quiz_length = optional_int(values["quiz_length"])
    if not quiz_length:
        errors.append("Default test length must be a whole number of at least 1.")
    pass_mark = optional_int(values["pass_mark"])
    if values["pass_mark"] and (pass_mark is None or not 0 <= pass_mark <= 100):
        errors.append("Pass mark must be a percentage from 0 to 100, or blank.")
    if errors:
        return _settings_page(request, bank, values, errors, status_code=422)

    bank.name = values["name"]
    bank.description = values["description"]
    bank.quiz_length = quiz_length
    bank.pass_mark = pass_mark
    session.add(bank)
    session.commit()
    return RedirectResponse(f"/banks/{bank.id}", status_code=303)


@router.post("/delete")
def delete_bank(session: SessionDep, user: CurrentUser, bank_id: int):
    session.delete(get_bank(session, user, bank_id))
    session.commit()
    return RedirectResponse("/", status_code=303)
