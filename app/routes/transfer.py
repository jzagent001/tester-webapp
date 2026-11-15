"""CSV import / export, plus the question-writing kit download."""

import io
import zipfile
from typing import Annotated

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, col, select

from app.auth import CurrentUser
from app.config import (
    DEFAULT_QUIZ_LENGTH,
    MAX_UPLOAD_BYTES,
    SAMPLE_CSV,
    WRITING_KIT_DIR,
)
from app.crud import (
    get_bank_by_name,
    import_csv_text,
    load_example_bank,
    question_count,
)
from app.csv_io import HEADER, ImportResult, to_csv
from app.db import SessionDep
from app.models import Bank, Question, User
from app.templating import get_bank, is_htmx, optional_int, templates

router = APIRouter(tags=["import-export"])


def _render(
    request: Request,
    session: Session,
    user: User,
    result: ImportResult | None = None,
    bank: Bank | None = None,
    selected_id: int | None = None,
    status_code: int = 200,
):
    context = {
        "result": result,
        "target": bank,
        "total": question_count(session, bank.id) if bank else 0,
        "banks": session.exec(
            select(Bank).where(Bank.owner_id == user.id).order_by(Bank.name)
        ).all(),
        "selected_id": selected_id,
        "header": ",".join(HEADER),
    }
    template = "transfer/_result.html" if is_htmx(request) and result else "transfer/import.html"
    return templates.TemplateResponse(request, template, context, status_code=status_code)


@router.get("/import")
def import_page(request: Request, session: SessionDep, user: CurrentUser, bank: str = ""):
    return _render(request, session, user, selected_id=optional_int(bank))


@router.post("/import")
async def import_csv(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    file: UploadFile,
    bank_id: Annotated[str, Form()] = "",
    new_bank: Annotated[str, Form()] = "",
    skip_duplicates: Annotated[bool, Form()] = False,
):
    def fail(message: str):
        return _render(
            request,
            session,
            user,
            ImportResult(errors=[message]),
            selected_id=optional_int(bank_id),
            status_code=422,
        )

    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        return fail(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Split it into smaller files.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return fail("The file is not UTF-8 text. Save it as “CSV UTF-8” and try again.")

    target_id = optional_int(bank_id)
    if target_id is not None:
        bank = session.get(Bank, target_id)
        if bank is None or bank.owner_id != user.id:
            return fail("That bank no longer exists.")
    else:
        name = new_bank.strip()
        if not name:
            return fail("Choose a bank to import into, or name a new one.")
        bank = get_bank_by_name(session, user.id, name)
        if bank is None:
            bank = Bank(owner_id=user.id, name=name, quiz_length=DEFAULT_QUIZ_LENGTH)
            session.add(bank)
            session.commit()
            session.refresh(bank)

    result = import_csv_text(session, bank, text, skip_duplicates)
    return _render(request, session, user, result, bank=bank, selected_id=bank.id)


@router.post("/import/example")
def import_example(request: Request, session: SessionDep, user: CurrentUser):
    bank, result = load_example_bank(session, user)
    return _render(request, session, user, result, bank=bank, selected_id=bank.id)


@router.get("/import/sample.csv")
def sample_csv():
    return FileResponse(SAMPLE_CSV, media_type="text/csv", filename="sample_questions.csv")


@router.get("/question-writing-kit.zip")
def writing_kit():
    """Zip of everything in `question writing instructions/`, built fresh on each request."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(WRITING_KIT_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, f"{WRITING_KIT_DIR.name}/{path.relative_to(WRITING_KIT_DIR)}")
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="question-writing-kit.zip"'},
    )


@router.get("/banks/{bank_id}/export.csv")
def export_csv(session: SessionDep, user: CurrentUser, bank_id: int):
    bank = get_bank(session, user, bank_id)
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
