import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
SAMPLE_CSV = DATA_DIR / "sample_questions.csv"
# Offered as one zip download ("question-writing-kit.zip") from the home and import pages.
WRITING_KIT_DIR = BASE_DIR / "question writing instructions"

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

# --- Sign-in -------------------------------------------------------------------------
# AUTH_MODE=single      everyone is SINGLE_USER_EMAIL (local use, or a LAN trial).
# AUTH_MODE=cloudflare  users sign in through Cloudflare Access; the app verifies the
#                       Cf-Access-Jwt-Assertion token Cloudflare adds to every request.
AUTH_MODE = os.environ.get("AUTH_MODE", "single").strip().lower()
# Use the email you will later sign in with through Cloudflare, so your banks carry over.
SINGLE_USER_EMAIL = os.environ.get("SINGLE_USER_EMAIL", "").strip().lower()
CF_ACCESS_TEAM_DOMAIN = os.environ.get("CF_ACCESS_TEAM_DOMAIN", "").strip()  # myteam.cloudflareaccess.com
CF_ACCESS_AUD = os.environ.get("CF_ACCESS_AUD", "").strip()  # the Access application's AUD tag

MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def settings_errors() -> list[str]:
    """Problems that stop the app from starting."""
    if AUTH_MODE == "single":
        return [] if SINGLE_USER_EMAIL else ["AUTH_MODE=single needs SINGLE_USER_EMAIL."]
    if AUTH_MODE == "cloudflare":
        return [
            f"AUTH_MODE=cloudflare needs {name}."
            for name, value in (
                ("CF_ACCESS_TEAM_DOMAIN", CF_ACCESS_TEAM_DOMAIN),
                ("CF_ACCESS_AUD", CF_ACCESS_AUD),
            )
            if not value
        ]
    return [f"AUTH_MODE must be 'single' or 'cloudflare', not {AUTH_MODE!r}."]
