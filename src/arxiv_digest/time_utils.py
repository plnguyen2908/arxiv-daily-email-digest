from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def current_day_cutoff_utc(timezone_name: str, now_utc: datetime | None = None) -> datetime:
    now = now_utc or datetime.now(timezone.utc)
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:
        zone = timezone.utc
    local_now = now.astimezone(zone)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc)


def latest_arxiv_announcement_cutoff_utc(now_utc: datetime | None = None) -> datetime:
    """Return latest arXiv announcement boundary in UTC.

    arXiv announces on US Eastern time at 20:00 on: Sunday, Monday, Tuesday,
    Wednesday, Thursday. This function finds the most recent such boundary.
    """

    now = now_utc or datetime.now(timezone.utc)
    eastern = ZoneInfo("America/New_York")
    local_now = now.astimezone(eastern)

    candidate = local_now.replace(hour=20, minute=0, second=0, microsecond=0)
    if candidate > local_now:
        candidate = candidate - timedelta(days=1)

    announcement_weekdays = {6, 0, 1, 2, 3}  # Sun, Mon, Tue, Wed, Thu
    while candidate.weekday() not in announcement_weekdays:
        candidate = candidate - timedelta(days=1)

    return candidate.astimezone(timezone.utc)
