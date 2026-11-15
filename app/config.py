import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
SAMPLE_CSV = DATA_DIR / "sample_questions.csv"

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")

DEFAULT_QUIZ_LENGTH = 20

# The bundled example bank, loaded by "Load the example bank" or `python -m app.seed`.
EXAMPLE_BANK = {
    "name": "Optical Networking Fundamentals",
    "description": (
        "Original practice questions on optical networking "
        "fundamentals: fibre, amplification, DWDM and transport networks."
    ),
    "quiz_length": 40,
    "files": [
        DATA_DIR / "examples" / "optical_networking_questions.csv",
        DATA_DIR / "examples" / "optical_networking_hard_questions.csv",
    ],
}
