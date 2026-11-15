"""Load the bundled example bank for one user.

    uv run python -m app.seed                 # for SINGLE_USER_EMAIL
    uv run python -m app.seed you@example.com
"""

import sys

from sqlmodel import Session

from app import config
from app.auth import get_or_create_user
from app.crud import load_example_bank
from app.db import engine
from app.migrate import upgrade


def main() -> None:
    email = (sys.argv[1] if len(sys.argv) > 1 else config.SINGLE_USER_EMAIL).strip().lower()
    if not email:
        sys.exit("Give an email address, or set SINGLE_USER_EMAIL.")
    upgrade(config.DATABASE_URL)
    with Session(engine) as session:
        bank, result = load_example_bank(session, get_or_create_user(session, email))
        print(f"{bank.name} ({email}): imported {result.imported}, skipped {result.skipped} duplicates.")
    for error in result.errors:
        print(error)


if __name__ == "__main__":
    main()
