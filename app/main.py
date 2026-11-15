from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import create_db_and_tables
from app.routes import banks, home, questions, quiz, topics, transfer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Self-Test", lifespan=lifespan)
app.include_router(home.router)
app.include_router(banks.router)
app.include_router(topics.router)
app.include_router(questions.router)
app.include_router(quiz.router)
app.include_router(transfer.router)
