from sqlmodel import Session, col, func, select

from app.config import EXAMPLE_BANK
from app.csv_io import ImportResult, QuestionData, parse_csv
from app.models import Bank, Choice, KnowledgePoint, Module, Question


def normalize(text: str) -> str:
    """Case- and whitespace-insensitive key for comparing names and question text."""
    return " ".join(text.lower().split())


# --- Questions ---------------------------------------------------------------


def apply_data(
    question: Question,
    data: QuestionData,
    module_id: int | None = None,
    knowledge_point_id: int | None = None,
) -> Question:
    """Copy validated form/CSV data onto a question, replacing its choices."""
    question.text = data.text.strip()
    question.explanation = data.explanation.strip()
    question.module_id = module_id
    question.knowledge_point_id = knowledge_point_id
    question.choices = [
        Choice(position=i, text=text.strip(), is_correct=correct)
        for i, (text, correct) in enumerate(data.choices)
    ]
    return question


def check_classification(
    session: Session, bank_id: int, module_id: int | None, knowledge_point_id: int | None
) -> list[str]:
    """Errors if the module/knowledge point ids don't fit together inside this bank."""
    if module_id is None:
        return ["A knowledge point needs a module."] if knowledge_point_id is not None else []
    module = session.get(Module, module_id)
    if module is None or module.bank_id != bank_id:
        return ["That module does not belong to this bank."]
    if knowledge_point_id is not None:
        point = session.get(KnowledgePoint, knowledge_point_id)
        if point is None or point.module_id != module_id:
            return ["That knowledge point does not belong to the chosen module."]
    return []


def question_count(session: Session, bank_id: int) -> int:
    return session.exec(
        select(func.count(col(Question.id))).where(Question.bank_id == bank_id)
    ).one()


def classification_counts(session: Session, bank_id: int) -> dict[tuple[int | None, int | None], int]:
    """Number of questions per (module_id, knowledge_point_id) in a bank."""
    rows = session.exec(
        select(Question.module_id, Question.knowledge_point_id, func.count(col(Question.id)))
        .where(Question.bank_id == bank_id)
        .group_by(Question.module_id, Question.knowledge_point_id)
    ).all()
    return {(m, k): n for m, k, n in rows}


# --- Modules and knowledge points --------------------------------------------


def _next_position(items) -> int:
    return max((i.position for i in items), default=-1) + 1


def find_module(bank: Bank, name: str) -> Module | None:
    key = normalize(name)
    return next((m for m in bank.modules if normalize(m.name) == key), None)


def find_point(module: Module, name: str) -> KnowledgePoint | None:
    key = normalize(name)
    return next((p for p in module.points if normalize(p.name) == key), None)


def module_name_error(bank: Bank, name: str, current: Module | None = None) -> str | None:
    if not name.strip():
        return "Module name is required."
    existing = find_module(bank, name)
    if existing is not None and existing is not current:
        return f"There is already a module called “{existing.name}”."
    return None


def point_name_error(
    module: Module, name: str, current: KnowledgePoint | None = None
) -> str | None:
    if not name.strip():
        return "Knowledge point name is required."
    existing = find_point(module, name)
    if existing is not None and existing is not current:
        return f"“{module.name}” already has a knowledge point called “{existing.name}”."
    return None


def add_module(session: Session, bank: Bank, name: str) -> Module:
    module = Module(bank_id=bank.id, name=name.strip(), position=_next_position(bank.modules))
    bank.modules.append(module)
    session.add(module)
    session.flush()
    return module


def add_point(session: Session, module: Module, name: str, description: str = "") -> KnowledgePoint:
    point = KnowledgePoint(
        module_id=module.id,
        name=name.strip(),
        description=description.strip(),
        position=_next_position(module.points),
    )
    module.points.append(point)
    session.add(point)
    session.flush()
    return point


def move(session: Session, siblings: list, item, direction: int) -> None:
    """Swap an item with its neighbour (direction -1 = up, +1 = down) and renumber."""
    order = list(siblings)
    i = order.index(item)
    j = i + direction
    if 0 <= j < len(order):
        order[i], order[j] = order[j], order[i]
    for pos, sibling in enumerate(order):
        sibling.position = pos
        session.add(sibling)
    session.commit()


# --- Import ------------------------------------------------------------------


class TopicResolver:
    """Finds modules/knowledge points by name, creating any that don't exist yet."""

    def __init__(self, session: Session, bank: Bank, result: ImportResult):
        self.session = session
        self.bank = bank
        self.result = result

    def resolve(self, module_name: str, point_name: str) -> tuple[int | None, int | None]:
        if not module_name.strip():
            return None, None
        module = find_module(self.bank, module_name)
        if module is None:
            module = add_module(self.session, self.bank, module_name)
            self.result.new_modules.append(module.name)
        if not point_name.strip():
            return module.id, None
        point = find_point(module, point_name)
        if point is None:
            point = add_point(self.session, module, point_name)
            self.result.new_points.append(f"{module.name} › {point.name}")
        return module.id, point.id


def import_questions(
    session: Session,
    bank: Bank,
    items: list[QuestionData],
    skip_duplicates: bool = True,
    result: ImportResult | None = None,
) -> ImportResult:
    """Insert questions into a bank. Duplicate detection only looks inside this bank."""
    result = result or ImportResult()
    resolver = TopicResolver(session, bank, result)
    existing = {
        normalize(t)
        for t in session.exec(select(Question.text).where(Question.bank_id == bank.id)).all()
    }
    for item in items:
        key = normalize(item.text)
        if skip_duplicates and key in existing:
            result.skipped += 1
            continue
        module_id, point_id = resolver.resolve(item.module, item.knowledge_point)
        session.add(apply_data(Question(bank_id=bank.id, text=""), item, module_id, point_id))
        existing.add(key)
        result.imported += 1
    session.commit()
    return result


def import_csv_text(
    session: Session, bank: Bank, text: str, skip_duplicates: bool = True
) -> ImportResult:
    items, errors = parse_csv(text)
    result = ImportResult(errors=errors)
    return import_questions(session, bank, items, skip_duplicates, result)


def get_bank_by_name(session: Session, name: str) -> Bank | None:
    key = normalize(name)
    return next((b for b in session.exec(select(Bank)).all() if normalize(b.name) == key), None)


def load_example_bank(session: Session) -> tuple[Bank, ImportResult]:
    bank = get_bank_by_name(session, EXAMPLE_BANK["name"])
    if bank is None:
        bank = Bank(
            name=EXAMPLE_BANK["name"],
            description=EXAMPLE_BANK["description"],
            quiz_length=EXAMPLE_BANK["quiz_length"],
        )
        session.add(bank)
        session.commit()
        session.refresh(bank)
    total = ImportResult()
    for path in EXAMPLE_BANK["files"]:
        items, errors = parse_csv(path.read_text(encoding="utf-8"))
        total.errors += [f"{path.name}: {e}" for e in errors]
        import_questions(session, bank, items, skip_duplicates=True, result=total)
    return bank, total
