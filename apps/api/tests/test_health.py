import os

import pytest
from httpx import AsyncClient

REQUIRE_DB = os.environ.get("REQUIRE_DB") == "1"


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] in {"ok", "unavailable"}


@pytest.mark.skipif(not REQUIRE_DB, reason="set REQUIRE_DB=1 with a reachable Postgres")
async def test_health_reports_db_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.json()["db"] == "ok"
