# Self-Test

Multiple-choice practice app for any exam or subject. Questions live in **banks**; each bank
is organised into **modules** and **knowledge points**, and every test result breaks down by
them so you can see your weak areas.

FastAPI + Jinja2 + HTMX + Pico.css (both from a CDN, no build step), stored in SQLite via SQLModel.

## Run

```bash
uv sync
export SINGLE_USER_EMAIL=you@example.com   # who you are when running locally (see "Users")
uv run fastapi dev app/main.py             # http://127.0.0.1:8000
uv run python -m app.seed                  # optional: load the example bank (Quantum Physics Fundamentals, 100 questions)
```

The database is `app.db` in the project root; set `DATABASE_URL` to use another. Schema
migrations run automatically at startup (or `uv run python -m app.migrate`).

## Users

The app has no accounts or passwords. Every bank belongs to one user, identified by email,
and nobody else can see it or their test results. Who you are depends on `AUTH_MODE`:

- `single` (default): everyone is `SINGLE_USER_EMAIL`. For local use and a LAN trial.
- `cloudflare`: users sign in through Cloudflare Access with an email code, and the app
  verifies Cloudflare's signed token on every request.

[DEPLOY.md](DEPLOY.md) covers running it in Docker on Unraid and putting it behind a
Cloudflare Tunnel + Access.

**Upgrading a database from before users existed** (e.g. your old local `app.db`): the first
start assigns its banks to `OWNER_EMAIL`, falling back to `SINGLE_USER_EMAIL`, and refuses to
start if neither is set.

## Test

```bash
uv run pytest
uv run pytest tests/test_quiz.py::test_results_breakdown
```

## Classifying questions

Each question is filed at one of three levels:

| module | knowledge point | meaning |
|---|---|---|
| blank | blank | general question for the bank |
| set | blank | general question within that module |
| set | set | that knowledge point |

Deleting a module or knowledge point keeps its questions and makes them general.

## Importing questions

CSV with a header row: `module,knowledge_point,question,A,B,C,D,E,F,G,H,correct,explanation`.

- `question`, `A`, `B` and `correct` are required; `C`–`H`, `explanation`, `module` and
  `knowledge_point` are optional.
- `correct` lists the letters of every correct choice, e.g. `B` or `A;C`.
- Modules and knowledge points are matched by name (ignoring case) and created if missing.
- Older files with a `topic` column are accepted; the topic becomes the module.

You pick the target bank (or name a new one) on the Import page. Duplicate detection only
looks inside that bank. See `data/sample_questions.csv`, also downloadable from the Import
page. Each bank's page has an *Export CSV* link that produces the same format.

## Writing your own question bank

The [`question writing instructions/`](question%20writing%20instructions/) folder has
everything needed to author a bank, by hand or with an LLM:

- `sample_question_bank.csv`: a complete, valid example that uses every feature (all three
  classification levels, single and multiple answers, 2 to 8 choices, quoting).
- `QUESTION_WRITING_GUIDE.md`: the rules for the LLM: how to research the subject, plan
  modules and knowledge points, the CSV format, question-writing guidance and a checklist.
- `PROMPT INSTRUCTION.md`: a two-step prompt template: the LLM researches and proposes a
  topic plan for your approval, then outputs only the CSV.
- `HOW TO USE.md`: step-by-step instructions for you: filling in the prompt, saving the
  reply, importing it and fixing rejected rows.

The home page and the Import page have a **Download the question-writing kit** button that
serves the whole folder as `question-writing-kit.zip`. The zip is built on each request, so
it always matches what's in the folder.

## About the example bank

`data/examples/quantum_physics_fundamentals.csv` holds 100 original questions on introductory
quantum physics, in 6 modules and 20 knowledge points: origins of quantum theory, wave-particle
duality, wavefunctions and measurement, simple potentials, atoms and spin, and superposition and
entanglement. Each user who loads it gets their own copy.

## Licence

Copyright (C) 2026 jzagent001. Licensed under the [GNU Affero General Public License v3.0 or
later](LICENSE). You may use, change and host it, but if you run a modified version that other
people use over a network, you must offer them its source code under the same licence.
