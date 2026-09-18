import secrets

from fastapi import APIRouter, Header, Request

from app.api.deps import DbSession
from app.config import get_settings
from app.errors import Unauthorized
from app.schemas import DispatchOut
from app.services.dispatch import run_dispatch
from app.services.senders import Senders

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/dispatch")
async def dispatch(
    request: Request, db: DbSession, x_cron_secret: str | None = Header(default=None)
) -> DispatchOut:
    expected = get_settings().cron_secret
    if not x_cron_secret or not secrets.compare_digest(x_cron_secret, expected):
        raise Unauthorized("bad cron secret")
    senders: Senders = request.app.state.senders
    counts = await run_dispatch(db, senders)
    return DispatchOut(**counts)
