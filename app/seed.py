"""Load the bundled example bank: `uv run python -m app.seed`."""

from sqlmodel import Session

from app.crud import load_example_bank
from app.db import create_db_and_tables, engine


def main() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        bank, result = load_example_bank(session)
        print(f"{bank.name}: imported {result.imported}, skipped {result.skipped} duplicates.")
    for error in result.errors:
        print(error)


if __name__ == "__main__":
    main()
