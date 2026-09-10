from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.jobs import router as jobs_router
from app.db import migrate, wait_for_database
from app.rabbitmq.client import wait_for_rabbitmq


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wait_for_database()
    migrate()
    wait_for_rabbitmq()
    yield


app = FastAPI(title="Domain Processing Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
