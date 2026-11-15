from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.config import TEMPLATES_DIR
from app.csv_io import LETTERS
from app.models import Bank

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["LETTERS"] = LETTERS


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def get_bank(session: Session, bank_id: int) -> Bank:
    bank = session.get(Bank, bank_id)
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found")
    return bank


def optional_int(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value.isdigit() else None
