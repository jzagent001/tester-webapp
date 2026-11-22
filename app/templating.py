from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app import config
from app.config import TEMPLATES_DIR
from app.csv_io import LETTERS
from app.models import Bank, User

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["LETTERS"] = LETTERS
templates.env.globals["auth_mode"] = lambda: config.AUTH_MODE
templates.env.globals["source_url"] = lambda: config.SOURCE_URL


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def get_bank(session: Session, user: User, bank_id: int) -> Bank:
    """The bank, if this user owns it. Anything else is a 404 (not 403), so IDs of other
    people's banks aren't confirmed to exist."""
    bank = session.get(Bank, bank_id)
    if bank is None or bank.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Bank not found")
    return bank


def optional_int(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value.isdigit() else None
