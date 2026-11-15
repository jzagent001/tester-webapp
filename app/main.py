from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text

from app import config
from app.auth import get_current_user
from app.db import SessionDep, create_db_and_tables, enable_wal
from app.migrate import upgrade
from app.routes import banks, home, questions, quiz, topics, transfer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if errors := config.settings_errors():
        raise RuntimeError("Can't start: " + " ".join(errors))
    if config.DATABASE_URL in ("sqlite://", "sqlite:///:memory:"):
        create_db_and_tables()  # throwaway in-memory database: nothing to migrate
    else:
        upgrade(config.DATABASE_URL)
        enable_wal(config.DATABASE_URL)
    yield


app = FastAPI(title="Self-Test", lifespan=lifespan)

# Every page needs a signed-in user. Routes that scope data also take `user: CurrentUser`;
# FastAPI resolves the dependency once per request either way.
signed_in = [Depends(get_current_user)]
for module in (home, banks, topics, questions, quiz, transfer):
    app.include_router(module.router, dependencies=signed_in)


@app.get("/healthz", include_in_schema=False)
def healthz(session: SessionDep):
    """Liveness check for Docker. No sign-in needed and reveals nothing."""
    session.exec(text("SELECT 1"))
    return {"ok": True}
