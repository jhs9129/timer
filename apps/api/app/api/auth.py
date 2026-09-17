from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import (
    DbSession,
    GoogleClient,
    clear_session_cookie,
    set_session_cookie,
)
from app.api.me import build_me
from app.config import get_settings
from app.errors import DomainError, NotFound
from app.models.user import User
from app.schemas import DevLoginIn, MeOut
from app.services.auth import (
    create_user,
    new_state,
    sign_state,
    upsert_google_user,
    verify_state,
)

router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "mlv_oauth_state"


@router.get("/google/start")
async def google_start(google: GoogleClient) -> RedirectResponse:
    settings = get_settings()
    state = new_state()
    response = RedirectResponse(google.authorize_url(state), status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        STATE_COOKIE,
        sign_state(state),
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/auth",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request, db: DbSession, google: GoogleClient, code: str, state: str
) -> RedirectResponse:
    settings = get_settings()
    cookie = request.cookies.get(STATE_COOKIE)
    if not cookie or not verify_state(cookie, state):
        raise DomainError("oauth state mismatch")
    profile = await google.exchange_code(code)
    user = await upsert_google_user(db, profile)
    response = RedirectResponse(settings.frontend_url, status_code=status.HTTP_302_FOUND)
    set_session_cookie(response, user)
    response.delete_cookie(STATE_COOKIE, path="/auth")
    return response


@router.post("/dev-login")
async def dev_login(body: DevLoginIn, db: DbSession, response: Response) -> MeOut:
    settings = get_settings()
    if not (settings.is_development and settings.dev_login_enabled):
        raise NotFound("not found")
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None:
        user = await create_user(
            db,
            google_sub=f"dev:{body.email}",
            email=body.email,
            display_name=body.display_name or body.email.split("@")[0],
        )
    set_session_cookie(response, user)
    return await build_me(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_session_cookie(response)
