from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, col, func, select

from app.auth import CurrentUser
from app.config import DEFAULT_QUIZ_LENGTH
from app.crud import get_bank_by_name
from app.db import SessionDep
from app.models import Bank, Question, User
from app.templating import templates

router = APIRouter(tags=["home"])


def _home(
    request: Request, session: Session, user: User, error: str | None = None, name: str = ""
):
    banks = session.exec(select(Bank).where(Bank.owner_id == user.id).order_by(Bank.name)).all()
    counts = dict(
        session.exec(
            select(Question.bank_id, func.count(col(Question.id)))
            .where(col(Question.bank_id).in_([b.id for b in banks]))
            .group_by(Question.bank_id)
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {"banks": [(b, counts.get(b.id, 0)) for b in banks], "error": error, "name": name},
        status_code=422 if error else 200,
    )


@router.get("/")
def home(request: Request, session: SessionDep, user: CurrentUser):
    return _home(request, session, user)


@router.post("/banks")
def create_bank(
    request: Request, session: SessionDep, user: CurrentUser, name: Annotated[str, Form()] = ""
):
    name = name.strip()
    if not name:
        return _home(request, session, user, error="Give the bank a name.")
    if get_bank_by_name(session, user.id, name):
        return _home(
            request, session, user, error=f"You already have a bank called “{name}”.", name=name
        )
    bank = Bank(owner_id=user.id, name=name, quiz_length=DEFAULT_QUIZ_LENGTH)
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return RedirectResponse(f"/banks/{bank.id}/topics", status_code=303)
