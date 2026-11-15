"""Question validation plus CSV import/export.

CSV format (header row required, column order and case do not matter):

    module,knowledge_point,question,A,B,C,D,E,F,G,H,correct,explanation

`module` and `knowledge_point` are optional: leave both blank for a general
question, or give only a module for a general question within that module.
A knowledge point needs a module. Choice columns C–H and `explanation` are
optional. `correct` lists the letters of every correct choice, e.g. `B` or `A;C`.

Older files with a `topic` column instead of `module` are accepted; the topic
becomes the module.
"""

import csv
import io
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

LETTERS = "ABCDEFGH"
MIN_CHOICES = 2
MAX_CHOICES = len(LETTERS)
HEADER = ["module", "knowledge_point", "question", *LETTERS, "correct", "explanation"]
REQUIRED_COLUMNS = ("question", "a", "b", "correct")
COLUMN_ALIASES = {"kp": "knowledge_point", "knowledgepoint": "knowledge_point"}


@dataclass
class QuestionData:
    text: str
    explanation: str = ""
    choices: list[tuple[str, bool]] = field(default_factory=list)  # (text, is_correct)
    module: str = ""  # names; only used by CSV import
    knowledge_point: str = ""


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    new_modules: list[str] = field(default_factory=list)
    new_points: list[str] = field(default_factory=list)  # "Module › Point"


def validate(data: QuestionData) -> list[str]:
    errors = []
    if not data.text.strip():
        errors.append("Question text is required.")
    if len(data.choices) < MIN_CHOICES:
        errors.append(f"Provide at least {MIN_CHOICES} choices.")
    if len(data.choices) > MAX_CHOICES:
        errors.append(f"Provide at most {MAX_CHOICES} choices.")
    if data.choices and not any(correct for _, correct in data.choices):
        errors.append("Mark at least one choice as correct.")
    if data.knowledge_point.strip() and not data.module.strip():
        errors.append("A knowledge point needs a module.")
    return errors


def _column_name(name: str) -> str:
    key = re.sub(r"[\s\-]+", "_", name.strip().lower())
    return COLUMN_ALIASES.get(key, key)


def parse_csv(text: str) -> tuple[list[QuestionData], list[str]]:
    """Return the valid questions and a list of per-line error messages."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["The file is empty."]
    columns = [_column_name(n) if n else "" for n in reader.fieldnames]
    if "module" not in columns and "topic" in columns:
        columns = ["module" if c == "topic" else c for c in columns]
    reader.fieldnames = columns
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        return [], [
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected header: {','.join(HEADER)}"
        ]

    items: list[QuestionData] = []
    errors: list[str] = []
    for raw in reader:
        row = {k: v.strip() for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}
        if not any(row.values()):
            continue

        letters = list(dict.fromkeys(ch.upper() for ch in row.get("correct", "") if ch.isalpha()))
        problems = []
        unknown = [letter for letter in letters if letter not in LETTERS]
        if unknown:
            problems.append(f"Unknown answer letter(s) {', '.join(unknown)} (use A–H).")
        for letter in letters:
            if letter in LETTERS and not row.get(letter.lower()):
                problems.append(f"Correct answer {letter} has no choice text.")

        data = QuestionData(
            text=row.get("question", ""),
            explanation=row.get("explanation", ""),
            module=row.get("module", ""),
            knowledge_point=row.get("knowledge_point", ""),
            choices=[
                (row[letter.lower()], letter in letters)
                for letter in LETTERS
                if row.get(letter.lower())
            ],
        )
        problems.extend(validate(data))
        if problems:
            errors.append(f"Line {reader.line_num}: {' '.join(problems)}")
        else:
            items.append(data)
    return items, errors


def to_csv(questions: Iterable) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    for q in questions:
        choices = list(q.choices)[:MAX_CHOICES]
        texts = [c.text for c in choices] + [""] * (MAX_CHOICES - len(choices))
        correct = ";".join(LETTERS[i] for i, c in enumerate(choices) if c.is_correct)
        writer.writerow(
            [
                q.module.name if q.module else "",
                q.knowledge_point.name if q.knowledge_point else "",
                q.text,
                *texts,
                correct,
                q.explanation,
            ]
        )
    return buffer.getvalue()
