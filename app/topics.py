"""Topic filters and per-topic score breakdowns.

A topic *token* names a slice of a bank's questions. Forms and query strings use them:

    none      general questions with no module
    m:<id>    every question in module <id>
    mg:<id>   questions in module <id> that have no knowledge point
    k:<id>    questions on knowledge point <id>

The quiz setup only offers the leaf tokens (none, mg, k), so every question falls
under exactly one of them.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, and_, false, or_
from sqlmodel import Session, col, select

from app.models import Attempt, AttemptItem, Bank, Question, User

GENERAL = "General"


def token_clause(token: str) -> ColumnElement[bool] | None:
    """SQL condition for a topic token, or None if the token is malformed."""
    if token == "none":
        return col(Question.module_id).is_(None)
    kind, _, raw = token.partition(":")
    if not raw.isdigit():
        return None
    value = int(raw)
    if kind == "m":
        return col(Question.module_id) == value
    if kind == "mg":
        return and_(col(Question.module_id) == value, col(Question.knowledge_point_id).is_(None))
    if kind == "k":
        return col(Question.knowledge_point_id) == value
    return None


def tokens_clause(tokens: Iterable[str]) -> ColumnElement[bool]:
    clauses = [c for c in map(token_clause, tokens) if c is not None]
    return or_(*clauses) if clauses else false()


@dataclass
class Leaf:
    token: str
    label: str  # short label shown under its module
    full_label: str
    count: int = 0


@dataclass
class ModuleGroup:
    module_id: int | None
    name: str
    leaves: list[Leaf] = field(default_factory=list)

    @property
    def count(self) -> int:
        return sum(leaf.count for leaf in self.leaves)


def topic_tree(bank: Bank, counts: dict | None = None) -> list[ModuleGroup]:
    """Modules in order, each with its knowledge points then its general bucket.

    The bank-wide "General" group comes last. `counts` maps (module_id, kp_id) to a
    question count, as returned by crud.classification_counts.
    """
    counts = counts or {}
    groups = []
    for module in bank.modules:
        group = ModuleGroup(module.id, module.name)
        for point in module.points:
            group.leaves.append(
                Leaf(
                    f"k:{point.id}",
                    point.name,
                    f"{module.name} › {point.name}",
                    counts.get((module.id, point.id), 0),
                )
            )
        group.leaves.append(
            Leaf(f"mg:{module.id}", GENERAL, f"{module.name} › {GENERAL}", counts.get((module.id, None), 0))
        )
        groups.append(group)
    groups.append(
        ModuleGroup(None, GENERAL, [Leaf("none", GENERAL, GENERAL, counts.get((None, None), 0))])
    )
    return groups


def scope_label(bank: Bank, tokens: list[str]) -> str:
    """Human-readable summary of the selected leaf tokens ("" means everything)."""
    tree = topic_tree(bank)
    all_leaves = [leaf for group in tree for leaf in group.leaves]
    if not tokens or set(tokens) >= {leaf.token for leaf in all_leaves}:
        return ""
    parts = []
    for group in tree:
        picked = [leaf for leaf in group.leaves if leaf.token in tokens]
        if not picked:
            continue
        if len(picked) == len(group.leaves) and group.module_id is not None:
            parts.append(group.name)
        else:
            parts.extend(leaf.full_label for leaf in picked)
    return "; ".join(parts)


# --- Score breakdowns --------------------------------------------------------


@dataclass
class Tally:
    correct: int = 0
    answered: int = 0
    total: int = 0

    def add(self, item: AttemptItem) -> None:
        self.total += 1
        if item.is_answered:
            self.answered += 1
            if item.is_correct:
                self.correct += 1

    @property
    def pct(self) -> int:
        """Percent correct out of all questions asked (skips count as wrong)."""
        return round(100 * self.correct / self.total) if self.total else 0

    @property
    def accuracy(self) -> int:
        """Percent correct out of questions answered."""
        return round(100 * self.correct / self.answered) if self.answered else 0


@dataclass
class BreakdownRow:
    name: str
    tally: Tally
    points: list[tuple[str, Tally]] = field(default_factory=list)


def _names(bank: Bank) -> tuple[dict[int, str], dict[int, str], list[int]]:
    modules = {m.id: m.name for m in bank.modules}
    points = {p.id: p.name for m in bank.modules for p in m.points}
    order = [m.id for m in bank.modules]
    return modules, points, order


def breakdown(bank: Bank, items: Iterable[AttemptItem]) -> list[BreakdownRow]:
    """Group test items by module, then knowledge point, using the copied classification."""
    module_names, point_names, order = _names(bank)
    by_module: dict[int | None, dict[int | None, Tally]] = defaultdict(lambda: defaultdict(Tally))
    for item in items:
        by_module[item.module_id][item.knowledge_point_id].add(item)

    point_order = [p.id for m in bank.modules for p in m.points]

    def sort_key(module_id):
        if module_id is None:
            return (2, 0)
        return (0, order.index(module_id)) if module_id in order else (1, module_id)

    def point_key(point_id):
        # Configured order first, then points deleted since, then the module's general bucket.
        if point_id is None:
            return (2, 0)
        return (0, point_order.index(point_id)) if point_id in point_order else (1, point_id)

    rows = []
    for module_id in sorted(by_module, key=sort_key):
        point_tallies = by_module[module_id]
        total = Tally()
        for tally in point_tallies.values():
            total.correct += tally.correct
            total.answered += tally.answered
            total.total += tally.total
        name = GENERAL if module_id is None else module_names.get(module_id, "(deleted module)")
        row = BreakdownRow(name, total)
        if module_id is not None:
            for point_id in sorted(point_tallies, key=point_key):
                tally = point_tallies[point_id]
                label = GENERAL if point_id is None else point_names.get(point_id, "(deleted)")
                row.points.append((label, tally))
        rows.append(row)
    return rows


def weak_points(
    session: Session, bank: Bank, user: User, min_answered: int = 3, limit: int = 5
) -> list[tuple[str, Tally]]:
    """This user's lowest-accuracy topics over every test they took on this bank."""
    module_names, point_names, _ = _names(bank)
    items = session.exec(
        select(AttemptItem)
        .join(Attempt)
        .where(
            Attempt.bank_id == bank.id,
            Attempt.user_id == user.id,
            col(AttemptItem.is_correct).is_not(None),
        )
    ).all()
    tallies: dict[tuple[int | None, int | None], Tally] = defaultdict(Tally)
    for item in items:
        tallies[(item.module_id, item.knowledge_point_id)].add(item)

    rows = []
    for (module_id, point_id), tally in tallies.items():
        if tally.answered < min_answered:
            continue
        if module_id is None:
            label = GENERAL
        elif module_id not in module_names:
            continue  # module deleted since
        elif point_id is None:
            label = f"{module_names[module_id]} › {GENERAL}"
        elif point_id in point_names:
            label = f"{module_names[module_id]} › {point_names[point_id]}"
        else:
            continue
        rows.append((label, tally))
    rows.sort(key=lambda r: (r[1].accuracy, -r[1].answered, r[0]))
    return rows[:limit]
