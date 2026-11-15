"""CSV import / export."""

from typing import Annotated

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, col, select

from app.config import DEFAULT_QUIZ_LENGTH, SAMPLE_CSV
from app.crud import (
    get_bank_by_name,
    import_csv_text,
    load_example_bank,
    question_count,
)
from app.csv_io import HEADER, ImportResult, to_csv
from app.db import SessionDep
from app.models import Bank, Question
from app.templating import get_bank, is_htmx, optional_int, templates

router = APIRouter(tags=["import-export"])


def _render(
    request: Request,
    session: Session,
    result: ImportResult | None = None,
    bank: Bank | None = None,
    selected_id: int | None = None,
    status_code: int = 200,
):
    context = {
        "result": result,
        "target": bank,
        "total": question_count(session, bank.id) if bank else 0,
        "banks": session.exec(select(Bank).order_by(Bank.name)).all(),
        "selected_id": selected_id,
        "header": ",".join(HEADER),
    }
    template = "transfer/_result.html" if is_htmx(request) and result else "transfer/import.html"
    return templates.TemplateResponse(request, template, context, status_code=status_code)


@router.get("/import")
def import_page(request: Request, session: SessionDep, bank: str = ""):
    return _render(request, session, selected_id=optional_int(bank))


@router.post("/import")
async def import_csv(
    request: Request,
    session: SessionDep,
    file: UploadFile,
    bank_id: Annotated[str, Form()] = "",
    new_bank: Annotated[str, Form()] = "",
    skip_duplicates: Annotated[bool, Form()] = False,
):
    def fail(message: str):
        return _render(
            request,
            session,
            ImportResult(errors=[message]),
            selected_id=optional_int(bank_id),
            status_code=422,
        )

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return fail("The file is not UTF-8 text. Save it as “CSV UTF-8” and try again.")

    target_id = optional_int(bank_id)
    if target_id is not None:
        bank = session.get(Bank, target_id)
        if bank is None:
            return fail("That bank no longer exists.")
    else:
        name = new_bank.strip()
        if not name:
            return fail("Choose a bank to import into, or name a new one.")
        bank = get_bank_by_name(session, name)
        if bank is None:
            bank = Bank(name=name, quiz_length=DEFAULT_QUIZ_LENGTH)
            session.add(bank)
            session.commit()
            session.refresh(bank)

    result = import_csv_text(session, bank, text, skip_duplicates)
    return _render(request, session, result, bank=bank, selected_id=bank.id)


@router.post("/import/example")
def import_example(request: Request, session: SessionDep):
    bank, result = load_example_bank(session)
    return _render(request, session, result, bank=bank, selected_id=bank.id)


@router.get("/import/sample.csv")
def sample_csv():
    return FileResponse(SAMPLE_CSV, media_type="text/csv", filename="sample_questions.csv")


@router.get("/banks/{bank_id}/export.csv")
def export_csv(session: SessionDep, bank_id: int):
    bank = get_bank(session, bank_id)
    questions = session.exec(
        select(Question)
        .where(Question.bank_id == bank.id)
        .order_by(col(Question.module_id).is_(None), Question.module_id, col(Question.id))
    ).all()
    filename = "".join(ch if ch.isalnum() else "_" for ch in bank.name).strip("_") or "questions"
    return Response(
        to_csv(questions),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )
