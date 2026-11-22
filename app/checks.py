"""Quality checks on a bank's questions.

Answer length: question writers (LLMs especially) tend to make the correct choice the
longest, because it collects the qualifiers that make it precisely true. Test-takers then
pick it from length alone. The question-writing guide aims for the correct choice being
the longest in about 1 in 10 to 1 in 4 questions; we warn only when it is clearly above.
"""

from dataclasses import dataclass

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models import Question

MIN_QUESTIONS = 10  # fewer checkable questions than this is too noisy to judge
MAX_SHARE = 1 / 3  # warn when the correct choice is the longest in more than this share
CLEAR_RATIO = 1.25  # a correct choice is "clearly longer" when it is at least this many
CLEAR_CHARS = 10  # times, and this many characters, longer than the longest wrong one


@dataclass
class LengthBias:
    checked: int  # single-answer questions with at least 3 choices
    longest: int  # of those, how many have the correct choice as the longest
    clear: list[Question]  # where it is clearly longer, worst first

    @property
    def percent(self) -> int:
        return round(100 * self.longest / self.checked)


def answer_length_bias(session: Session, bank_id: int) -> LengthBias | None:
    """The bank's answer-length bias, or None when there is nothing to warn about."""
    questions = session.exec(
        select(Question)
        .where(Question.bank_id == bank_id)
        .options(selectinload(Question.choices))  # type: ignore[arg-type]
    ).all()
    checked = longest = 0
    clear: list[tuple[float, Question]] = []
    for question in questions:
        correct = [c for c in question.choices if c.is_correct]
        wrong = [c for c in question.choices if not c.is_correct]
        # Multiple-answer questions have no single "correct choice" to compare.
        if len(correct) != 1 or len(wrong) < 2:
            continue
        checked += 1
        right = len(correct[0].text.strip())
        top = max(len(c.text.strip()) for c in wrong)
        if right > top:
            longest += 1
            if right >= CLEAR_RATIO * top and right - top >= CLEAR_CHARS:
                clear.append((right / max(top, 1), question))
    if checked < MIN_QUESTIONS or longest / checked <= MAX_SHARE:
        return None
    clear.sort(key=lambda pair: pair[0], reverse=True)
    return LengthBias(checked, longest, [q for _, q in clear])
