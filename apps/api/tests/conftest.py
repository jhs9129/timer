from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import engine
from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    # ASGITransport does not run the lifespan, so release pooled connections here;
    # each test runs on its own event loop and asyncpg connections are loop-bound.
    await engine.dispose()
