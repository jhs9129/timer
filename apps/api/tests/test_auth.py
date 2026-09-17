from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_google_client
from app.main import app
from app.models.event import Event
from app.models.user import User
from app.models.village import Village
from app.services.auth import GoogleProfile


class FakeGoogle:
    def __init__(self, profile: GoogleProfile) -> None:
        self.profile = profile

    def authorize_url(self, state: str) -> str:
        return f"https://google.test/auth?state={state}"

    async def exchange_code(self, code: str) -> GoogleProfile:
        assert code == "good-code"
        return self.profile


PROFILE = GoogleProfile(sub="g-123", email="jane@example.com", name="Jane")


def _use_fake_google(profile: GoogleProfile = PROFILE) -> None:
    app.dependency_overrides[get_google_client] = lambda: FakeGoogle(profile)


async def _oauth_login(client: AsyncClient) -> None:
    start = await client.get("/auth/google/start")
    assert start.status_code == 302
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    cb = await client.get("/auth/google/callback", params={"code": "good-code", "state": state})
    assert cb.status_code == 302, cb.text


async def test_me_requires_login(anon_client: AsyncClient) -> None:
    res = await anon_client.get("/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


async def test_google_callback_creates_user_village_and_cookie(
    anon_client: AsyncClient, db: AsyncSession, fake_clock: object
) -> None:
    _use_fake_google()
    try:
        await _oauth_login(anon_client)
    finally:
        app.dependency_overrides.clear()

    me = await anon_client.get("/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "jane@example.com"
    assert body["balance"] == 0
    assert body["village"]["slug"]

    users = await db.execute(select(func.count()).select_from(User))
    assert users.scalar_one() == 1
    villages = await db.execute(select(Village).where(Village.owner_type == "user"))
    assert villages.scalar_one().owner_id == users_first_id(body)

    types = await db.execute(select(Event.event_type).order_by(Event.ingested_at))
    assert list(types.scalars().all()) == ["user.created", "village.created"]


def users_first_id(me_body: dict[str, object]) -> object:
    import uuid

    return uuid.UUID(str(me_body["id"]))


async def test_google_login_twice_does_not_duplicate_user(
    anon_client: AsyncClient, db: AsyncSession, fake_clock: object
) -> None:
    _use_fake_google()
    try:
        await _oauth_login(anon_client)
        await _oauth_login(anon_client)
    finally:
        app.dependency_overrides.clear()
    users = await db.execute(select(func.count()).select_from(User))
    assert users.scalar_one() == 1


async def test_google_callback_rejects_state_mismatch(
    anon_client: AsyncClient, db: AsyncSession, fake_clock: object
) -> None:
    _use_fake_google()
    try:
        start = await anon_client.get("/auth/google/start")
        assert start.status_code == 302
        cb = await anon_client.get(
            "/auth/google/callback", params={"code": "good-code", "state": "forged"}
        )
    finally:
        app.dependency_overrides.clear()
    assert cb.status_code == 400
    users = await db.execute(select(func.count()).select_from(User))
    assert users.scalar_one() == 0


async def test_dev_login_creates_user_in_development(
    anon_client: AsyncClient, fake_clock: object
) -> None:
    res = await anon_client.post("/auth/dev-login", json={"email": "dev@example.com"})
    assert res.status_code == 200, res.text
    assert res.json()["display_name"] == "dev"
    me = await anon_client.get("/me")
    assert me.status_code == 200


async def test_dev_login_hidden_outside_development(
    anon_client: AsyncClient, monkeypatch: object
) -> None:
    from app.config import get_settings

    settings = get_settings()
    original = settings.app_env
    settings.app_env = "production"
    try:
        res = await anon_client.post("/auth/dev-login", json={"email": "dev@example.com"})
    finally:
        settings.app_env = original
    assert res.status_code == 404


async def test_patch_me_rejects_bad_timezone(client: AsyncClient) -> None:
    res = await client.patch("/me", json={"timezone": "Mars/Olympus"})
    assert res.status_code == 422


async def test_patch_me_updates_timezone_and_name(client: AsyncClient) -> None:
    res = await client.patch("/me", json={"timezone": "Europe/Berlin", "display_name": "J"})
    assert res.status_code == 200, res.text
    assert res.json()["timezone"] == "Europe/Berlin"
    assert res.json()["display_name"] == "J"
