# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                   # install deps (Python 3.14)
SINGLE_USER_EMAIL=you@example.com uv run fastapi dev app/main.py   # dev server on :8000, ./app.db
uv run python -m app.seed [email]         # load the example quantum physics bank for a user
uv run python -m app.migrate              # apply migrations (also runs at startup)
uv run alembic revision --autogenerate -m "..."   # new migration after changing app/models.py
uv run pytest                             # all tests
uv run pytest tests/test_quiz.py::test_results_breakdown   # one test
```

No build step: Pico.css and HTMX load from a CDN in `templates/base.html`. Deployment (Docker on
Unraid, Cloudflare Tunnel + Access) is in `DEPLOY.md`; `podman build --format docker -t tester-webapp .`
builds the image locally.

## Architecture

FastAPI + Jinja2 server-rendered pages, HTMX for partial updates, SQLModel on SQLite.

**Migrations (`migrations/`, `app/migrate.py`)**: Alembic, run at startup by `app.main`'s lifespan
(tests use `create_all` on in-memory DBs instead). `0001` is the pre-users schema; `app.migrate`
stamps databases that predate Alembic as `0001` before upgrading. Autogenerate can't drop unnamed
SQLite constraints or backfill NOT NULL columns, so check every generated migration and hand-write
table rebuilds (see `0002`). `migrations/env.py` runs without `foreign_keys=ON` (rebuilds would
otherwise cascade-delete) and makes each migration one transaction. `tests/test_migrations.py`
diffs the migrated schema against the models: a model change without a migration fails it.

**Users (`app/auth.py`)**: no accounts or passwords. `AUTH_MODE=single` makes every request
`SINGLE_USER_EMAIL`; `AUTH_MODE=cloudflare` verifies the Cloudflare Access JWT
(`Cf-Access-Jwt-Assertion` header or `CF_Authorization` cookie) and takes the email from it. Never
trust the plain email header. `get_current_user` creates the `User` row on first sight and is a
dependency on every router (`app/main.py`); only `/healthz` is open. Settings are read from
`app.config` at call time and validated at startup (`config.settings_errors`).

**Ownership**: every `Bank` has `owner_id`; every `Attempt` has `user_id` (who took it). Always fetch
banks with `templating.get_bank(session, user, bank_id)` and attempts with `quiz._get_attempt`: they
return 404 for other users' rows. Lists (home, import page, name lookups, dashboard attempts, weak
points) filter by user explicitly. Bank names are unique per owner. `tests/test_isolation.py` hits
every route as a second user and expects 404, so add new routes to its list.

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

**Tests**: `tests/conftest.py` sets `DATABASE_URL=sqlite://` and single-user mode before importing
the app, and overrides `get_session` with an in-memory session per test. Requests run as alice by
default; the `act_as("bob@example.com")` fixture switches user. Fixtures `user`, `other_user`,
`make_bank`, `bank`, `topics` (module "Optics" with points "Loss", "Dispersion") and
`make_question`; `form_for()` builds question-form payloads. `tests/test_auth.py` signs real JWTs
with a test RSA key and stubs the JWKS fetch.
