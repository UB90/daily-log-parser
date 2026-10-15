"""Week generator: pure date math. No plan data.

Everything here works on dates and week numbers only, so any plan file
"""

from __future__ import annotations

import datetime as dt
from typing import List, Optional, Tuple

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_FULL = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
    "thu": "Thursday", "fri": "Friday", "sat": "Saturday",
    "sun": "Sunday",
}
DAY_KEY = {  # full lowercase name -> abbrev
    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat",
    "sunday": "sun",
}
WEEKDAYS = DAY_ORDER[:5]  # mon-fri


def parse_date(text: str) -> dt.date:
    """Parse YYYY-MM-DD (raises ValueError with a helpful message)."""
    try:
        return dt.date.fromisoformat(text.strip())
    except ValueError as exc:
        raise ValueError(
            "Bad date '" + str(text) + "' - use YYYY-MM-DD, e.g. 2026-10-15"
        ) from exc


def fmt_date(d: dt.date) -> str:
    return d.isoformat()


def parse_time(text: str) -> dt.time:
    """Parse HH:MM (raises ValueError with a helpful message)."""
    try:
        parts = str(text).strip().split(":")
        if not 2 <= len(parts) <= 3:
            raise ValueError
        return dt.time(int(parts[0]), int(parts[1]))
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "Bad time '" + str(text) + "' - use HH:MM, e.g. 22:30"
        ) from exc


def week_str(n: int) -> str:
    return "W" + str(n)


def week_number(week: str) -> int:
    """'W12' -> 12 (accepts lowercase, plain digits)."""
    text = str(week).strip()
    if text.lower().startswith("w"):
        text = text[1:]
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError("Bad week '" + str(week) + "' - use W12 or 12") from exc


def week_dates(start_date: str, total_weeks: int) -> List[Tuple[int, dt.date, dt.date]]:
    """[(1, start, end), ...] - every week starts Monday, ends Sunday."""
    start = parse_date(start_date)
    # normalize to Monday
    offset = (start.weekday()) % 7  # Monday=0 ... Sunday=6
    start = start - dt.timedelta(days=offset)
    out = []
    for i in range(total_weeks):
        s = start + dt.timedelta(days=7 * i)
        e = s + dt.timedelta(days=6)
        out.append((i + 1, s, e))
    return out


def date_to_day_abbrev(d: dt.date) -> str:
    return DAY_ORDER[d.weekday()]


def detect_week(plan: dict, today: Optional[dt.date] = None) -> int:
    """Find the week whose [start, end] contains today.

    Before week 1 -> 1. After the last week -> the last week.
    """
    if today is None:
        today = dt.date.today()
    weeks = plan.get("weeks", {})
    best = 1
    total = plan.get("total_weeks") or len(weeks) or 0
    for no in range(1, total + 1):
        w = weeks.get(week_str(no))
        if not w or not w.get("start_date"):
            continue
        try:
            s = parse_date(w["start_date"])
            e = parse_date(w.get("end_date") or w["start_date"])
        except ValueError:
            continue
        if s <= today:
            best = no
    if total == 0:
        return 1
    return max(1, min(best, total))
