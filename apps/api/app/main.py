from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, internal, me, sessions
from app.config import get_settings
from app.db import check_db, engine
from app.errors import install_error_handlers


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(title="My Little Village API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(sessions.router)
app.include_router(internal.router)


@app.get("/health")
async def health() -> dict[str, str]:
    db_ok = await check_db()
    return {"status": "ok", "db": "ok" if db_ok else "unavailable"}
