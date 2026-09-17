import secrets
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import Unauthorized
from app.models.user import User
from app.models.village import OWNER_USER
from app.services import clock
from app.services.events import emit
from app.services.villages import create_village

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _signer(salt: str) -> TimestampSigner:
    return TimestampSigner(get_settings().session_secret, salt=salt)


def sign_user_id(user_id: uuid.UUID) -> str:
    return _signer("session").sign(str(user_id)).decode()


def verify_session_token(token: str) -> uuid.UUID | None:
    try:
        raw = _signer("session").unsign(token, max_age=get_settings().cookie_max_age_seconds)
        return uuid.UUID(raw.decode())
    except (BadSignature, SignatureExpired, ValueError):
        return None


def sign_state(state: str) -> str:
    return _signer("oauth-state").sign(state).decode()


def verify_state(token: str, expected: str) -> bool:
    try:
        raw = _signer("oauth-state").unsign(token, max_age=600)
    except (BadSignature, SignatureExpired):
        return False
    return secrets.compare_digest(raw.decode(), expected)


@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str
    name: str


class GoogleOAuthClient:
    """Authorization-code flow against Google. Tests replace this with a fake."""

    def authorize_url(self, state: str) -> str:
        settings = get_settings()
        query = urlencode(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": settings.google_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"{GOOGLE_AUTH_URL}?{query}"

    async def exchange_code(self, code: str) -> GoogleProfile:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=10) as http:
            token_res = await http.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_res.status_code != 200:
                raise Unauthorized("google token exchange failed")
            access_token = token_res.json().get("access_token")
            if not access_token:
                raise Unauthorized("google token response missing access_token")
            info_res = await http.get(
                GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            if info_res.status_code != 200:
                raise Unauthorized("google userinfo failed")
            info = info_res.json()
        return GoogleProfile(
            sub=str(info["sub"]),
            email=str(info.get("email", "")),
            name=str(info.get("name") or info.get("email", "")),
        )


def new_state() -> str:
    return secrets.token_urlsafe(24)


async def upsert_google_user(db: AsyncSession, profile: GoogleProfile) -> User:
    result = await db.execute(select(User).where(User.google_sub == profile.sub))
    user = result.scalar_one_or_none()
    now = clock.now()
    if user is not None:
        user.updated_at = now
        return user
    return await create_user(
        db, google_sub=profile.sub, email=profile.email, display_name=profile.name
    )


async def create_user(
    db: AsyncSession, *, google_sub: str, email: str, display_name: str, timezone: str | None = None
) -> User:
    settings = get_settings()
    now = clock.now()
    user = User(
        google_sub=google_sub,
        email=email,
        display_name=display_name[:100] or email.split("@")[0],
        timezone=timezone or settings.default_timezone,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()
    emit(
        db,
        "user.created",
        subject_type="user",
        subject_id=user.id,
        actor_id=user.id,
        payload={"email_domain": email.rsplit("@", 1)[-1], "timezone": user.timezone},
    )
    await create_village(
        db, owner_type=OWNER_USER, owner_id=user.id, name=f"{user.display_name}의 마을"
    )
    return user
