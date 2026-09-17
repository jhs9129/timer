from httpx import AsyncClient


async def test_health_reports_db_ok(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}
