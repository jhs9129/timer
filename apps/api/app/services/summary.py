import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import KIND_SESSION_REWARD, CoinLedger
from app.models.session import STATUS_COMPLETED, FocusSession
from app.services.rewards import streak_days


@dataclass(frozen=True)
class WeeklySummary:
    start: str
    end: str
    focused_minutes: int
    completed_sessions: int
    coins: int
    streak_days: int

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


async def weekly_summary(db: AsyncSession, user_id: uuid.UUID, today: date) -> WeeklySummary:
    """The seven local days before `today` (today itself is still in progress)."""
    end = today - timedelta(days=1)
    start = end - timedelta(days=6)
    sessions = await db.execute(
        select(
            func.coalesce(func.sum(FocusSession.focused_seconds), 0),
            func.count(FocusSession.id),
        ).where(
            FocusSession.user_id == user_id,
            FocusSession.status == STATUS_COMPLETED,
            FocusSession.local_date.between(start, end),
        )
    )
    seconds, count = sessions.one()
    coins = await db.execute(
        select(func.coalesce(func.sum(CoinLedger.delta), 0)).where(
            CoinLedger.user_id == user_id,
            CoinLedger.kind == KIND_SESSION_REWARD,
            CoinLedger.local_date.between(start, end),
        )
    )
    return WeeklySummary(
        start=start.isoformat(),
        end=end.isoformat(),
        focused_minutes=int(seconds) // 60,
        completed_sessions=int(count),
        coins=int(coins.scalar_one()),
        streak_days=await streak_days(db, user_id, end),
    )


def render_weekly(display_name: str, s: dict[str, Any]) -> tuple[str, str, str]:
    """Returns (subject, text, html)."""
    hours, minutes = divmod(int(s["focused_minutes"]), 60)
    subject = f"지난주 몰두 요약 ({s['start']} ~ {s['end']})"
    lines = [
        f"{display_name}님, 지난주 몰두 기록이에요.",
        "",
        f"몰두 시간: {hours}시간 {minutes}분",
        f"완료한 세션: {s['completed_sessions']}회",
        f"얻은 코인: {s['coins']}",
        f"연속 일수: {s['streak_days']}일",
        "",
        "오늘의 작은 몰두가 내일의 마을을 만들어요.",
    ]
    text = "\n".join(lines)
    html = "<p>" + "</p><p>".join(line or "&nbsp;" for line in lines) + "</p>"
    return subject, text, html
