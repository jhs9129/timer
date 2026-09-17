from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def local_date_for(moment: datetime, tz_name: str, boundary_hour: int) -> date:
    """The user's 'day' for a UTC instant. A day starts at boundary_hour local time."""
    local = moment.astimezone(ZoneInfo(tz_name))
    return (local - timedelta(hours=boundary_hour)).date()
