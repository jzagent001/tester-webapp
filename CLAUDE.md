# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                   # install deps (Python 3.14)
uv run fastapi dev app/main.py            # dev server on :8000, uses ./app.db
uv run python -m app.seed                 # load the example optical networking bank
uv run pytest                             # all tests
uv run pytest tests/test_quiz.py::test_results_breakdown   # one test
```

No build step: Pico.css and HTMX load from a CDN in `templates/base.html`.

## Architecture

FastAPI + Jinja2 server-rendered pages, HTMX for partial updates, SQLModel on SQLite.
There are no migrations: `create_db_and_tables()` runs `create_all` at startup, so a schema
change needs a fresh `app.db`.

**Data model (`app/models.py`)**: `Bank` → `Module` → `KnowledgePoint`. A `Question` belongs to a bank
and has nullable `module_id` / `knowledge_point_id` (both null = general question for the bank;
module only = general within the module). Invariant: if `knowledge_point_id` is set, `module_id`
equals that point's module. `crud.check_classification` enforces this on form saves;
`crud.TopicResolver` keeps it on CSV import by creating modules/points by name. Deleting a module
or point relies on DB-level `ON DELETE SET NULL` (SQLite `PRAGMA foreign_keys=ON` is set in
`app/db.py`), so questions survive as general ones.

**Tests snapshot classification**: `Attempt` has ordered `AttemptItem` rows that copy
`question_id`, `module_id` and `knowledge_point_id` at test start, with no foreign keys, so results
and per-topic scores survive question edits and deletions. An item is unanswered while
`is_correct is None`; the first submitted answer is final.

**Topic tokens (`app/topics.py`)**: filters and quiz scopes are strings: `none`, `m:<id>` (whole
module), `mg:<id>` (module, no knowledge point), `k:<id>`. `token_clause` turns them into SQL;
`topic_tree` builds the module/leaf structure used by the question filter, quiz setup and dashboard;
`breakdown` and `weak_points` compute per-topic scores from `AttemptItem`s.

**Routes (`app/routes/`)**: bank-scoped pages live under `/banks/{bank_id}/...`; routes must check
that a fetched module/point/question belongs to that bank (404 otherwise). Test-taking pages are
`/quiz/{attempt_id}/...` and get the bank from the attempt. Templates render the per-bank sub-nav
whenever `bank` is in the context, so global pages (home, import) pass the bank under another name.

**HTMX conventions**: `is_htmx(request)` picks a fragment template (`_*.html`) over the full page;
`base.html` configures HTMX to swap 422 responses so validation errors render in place. Non-HTMX
form posts redirect with 303.

**CSV (`app/csv_io.py`)**: header names are normalised (case, spaces → `_`, `kp` alias), and a legacy
`topic` column maps to `module`. Duplicate detection (`crud.normalize` on question text) is per bank.

**Tests**: `tests/conftest.py` sets `DATABASE_URL=sqlite://` before importing the app and overrides
`get_session` with an in-memory session per test. Fixtures `bank`, `topics` (module "Optics" with
points "Loss", "Dispersion") and `make_question`; `form_for()` builds question-form payloads.
