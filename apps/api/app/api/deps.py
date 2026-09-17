from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import Unauthorized
from app.models.user import User
from app.services.auth import GoogleOAuthClient, sign_user_id, verify_session_token

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def current_user(request: Request, db: DbSession) -> User:
    token = request.cookies.get(get_settings().cookie_name)
    user_id = verify_session_token(token) if token else None
    if user_id is None:
        raise Unauthorized("login required")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise Unauthorized("login required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def get_google_client() -> GoogleOAuthClient:
    return GoogleOAuthClient()


GoogleClient = Annotated[GoogleOAuthClient, Depends(get_google_client)]


def set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=sign_user_id(user.id),
        max_age=settings.cookie_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
    )
