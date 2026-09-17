import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.models.user import User
from app.services import clock
from app.services.auth import create_user, sign_user_id

API_DIR = Path(__file__).resolve().parent.parent

DOMAIN_TABLES = [
    "retro_tags",
    "tags",
    "retrospectives",
    "coin_ledger",
    "session_segments",
    "focus_sessions",
    "villages",
    "events",
    "users",
]


def _split_url(url: str) -> tuple[str, str]:
    """Return (asyncpg DSN for the admin database, target database name)."""
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    base, _, dbname = dsn.rpartition("/")
    return f"{base}/postgres", dbname


async def _ensure_database(url: str) -> None:
    admin_dsn, dbname = _split_url(url)
    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", dbname)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def _migrated_database() -> AsyncIterator[None]:
    url = get_settings().database_url
    await _ensure_database(url)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        check=True,
        capture_output=True,
    )
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_tables(_migrated_database: None) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(DOMAIN_TABLES)} CASCADE"))


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)

    def set(self, moment: datetime) -> None:
        self.current = moment


# 2026-09-17 01:00 UTC == 10:00 Asia/Seoul, local_date 2026-09-17.
DEFAULT_START = datetime(2026, 9, 17, 1, 0, tzinfo=UTC)


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeClock]:
    fake = FakeClock(DEFAULT_START)
    monkeypatch.setattr(clock, "now", fake.now)
    yield fake


@pytest.fixture
async def user(fake_clock: FakeClock) -> User:
    async with SessionLocal() as session:
        created = await create_user(
            session,
            google_sub=f"test:{uuid.uuid4()}",
            email=f"user-{uuid.uuid4().hex[:8]}@test.dev",
            display_name="Tester",
            timezone="Asia/Seoul",
        )
        await session.commit()
        return created


@pytest.fixture
async def anon_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client(anon_client: AsyncClient, user: User) -> AsyncClient:
    anon_client.cookies.set(get_settings().cookie_name, sign_user_id(user.id))
    return anon_client


@pytest.fixture
async def other_client(fake_clock: FakeClock) -> AsyncIterator[AsyncClient]:
    async with SessionLocal() as session:
        other = await create_user(
            session,
            google_sub=f"test:{uuid.uuid4()}",
            email=f"other-{uuid.uuid4().hex[:8]}@test.dev",
            display_name="Other",
            timezone="Asia/Seoul",
        )
        await session.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.cookies.set(get_settings().cookie_name, sign_user_id(other.id))
        yield ac
