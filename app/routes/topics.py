"""Managing a bank's modules and knowledge points."""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.crud import (
    add_module,
    add_point,
    classification_counts,
    module_name_error,
    move,
    point_name_error,
)
from app.db import SessionDep
from app.models import Bank, KnowledgePoint, Module
from app.templating import get_bank, templates

router = APIRouter(prefix="/banks/{bank_id}", tags=["topics"])


def _page(request: Request, session: Session, bank: Bank, error: str | None = None):
    return templates.TemplateResponse(
        request,
        "topics/index.html",
        {"bank": bank, "counts": classification_counts(session, bank.id), "error": error},
        status_code=422 if error else 200,
    )


def _back(bank: Bank, anchor: str = "") -> RedirectResponse:
    return RedirectResponse(f"/banks/{bank.id}/topics{anchor}", status_code=303)


def _module(session: Session, bank: Bank, module_id: int) -> Module:
    module = session.get(Module, module_id)
    if module is None or module.bank_id != bank.id:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


def _point(session: Session, bank: Bank, point_id: int) -> KnowledgePoint:
    point = session.get(KnowledgePoint, point_id)
    if point is None or point.module.bank_id != bank.id:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    return point


Name = Annotated[str, Form()]
Direction = Annotated[int, Form(ge=-1, le=1)]


@router.get("/topics")
def topics_page(request: Request, session: SessionDep, bank_id: int):
    return _page(request, session, get_bank(session, bank_id))


@router.post("/modules")
def create_module(request: Request, session: SessionDep, bank_id: int, name: Name = ""):
    bank = get_bank(session, bank_id)
    if error := module_name_error(bank, name):
        return _page(request, session, bank, error)
    module = add_module(session, bank, name)
    session.commit()
    return _back(bank, f"#module-{module.id}")


@router.post("/modules/{module_id}")
def rename_module(
    request: Request, session: SessionDep, bank_id: int, module_id: int, name: Name = ""
):
    bank = get_bank(session, bank_id)
    module = _module(session, bank, module_id)
    if error := module_name_error(bank, name, current=module):
        return _page(request, session, bank, error)
    module.name = name.strip()
    session.add(module)
    session.commit()
    return _back(bank, f"#module-{module.id}")


@router.post("/modules/{module_id}/move")
def move_module(session: SessionDep, bank_id: int, module_id: int, direction: Direction = 0):
    bank = get_bank(session, bank_id)
    module = _module(session, bank, module_id)
    move(session, bank.modules, module, direction)
    return _back(bank, f"#module-{module.id}")


@router.post("/modules/{module_id}/delete")
def delete_module(session: SessionDep, bank_id: int, module_id: int):
    bank = get_bank(session, bank_id)
    session.delete(_module(session, bank, module_id))
    session.commit()
    return _back(bank)


@router.post("/modules/{module_id}/points")
def create_point(
    request: Request,
    session: SessionDep,
    bank_id: int,
    module_id: int,
    name: Name = "",
    description: Name = "",
):
    bank = get_bank(session, bank_id)
    module = _module(session, bank, module_id)
    if error := point_name_error(module, name):
        return _page(request, session, bank, error)
    add_point(session, module, name, description)
    session.commit()
    return _back(bank, f"#module-{module.id}")


@router.post("/points/{point_id}")
def update_point(
    request: Request,
    session: SessionDep,
    bank_id: int,
    point_id: int,
    name: Name = "",
    description: Name = "",
):
    bank = get_bank(session, bank_id)
    point = _point(session, bank, point_id)
    if error := point_name_error(point.module, name, current=point):
        return _page(request, session, bank, error)
    point.name = name.strip()
    point.description = description.strip()
    session.add(point)
    session.commit()
    return _back(bank, f"#module-{point.module_id}")


@router.post("/points/{point_id}/move")
def move_point(session: SessionDep, bank_id: int, point_id: int, direction: Direction = 0):
    bank = get_bank(session, bank_id)
    point = _point(session, bank, point_id)
    move(session, point.module.points, point, direction)
    return _back(bank, f"#module-{point.module_id}")


@router.post("/points/{point_id}/delete")
def delete_point(session: SessionDep, bank_id: int, point_id: int):
    bank = get_bank(session, bank_id)
    point = _point(session, bank, point_id)
    module_id = point.module_id
    session.delete(point)
    session.commit()
    return _back(bank, f"#module-{module_id}")
