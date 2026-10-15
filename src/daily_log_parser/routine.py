"""Routine: structural defaults only. Zero plan data here.

If a plan file is missing some metadata (task type icons, day-type colors),
these generic fallbacks are used so the CLI never crashes on a user-made
plan. The real look-and-feel lives inside each plan's JSON.
"""

from __future__ import annotations

# Fallback task-type metadata (label / rich color / icon).
DEFAULT_TASK_TYPE_META = {
    "ship":   {"label": "Ship",   "color": "green",   "icon": "\u25c6"},
    "setup":  {"label": "Setup",  "color": "blue",    "icon": "\u2699"},
    "learn":  {"label": "Learn",  "color": "cyan",    "icon": "\u25c7"},
    "review": {"label": "Review", "color": "yellow",  "icon": "\u25cb"},
    "anki":   {"label": "Anki",   "color": "magenta", "icon": "\u25a3"},
    "log":    {"label": "Log",    "color": "bright_black", "icon": "\u25b8"},
    "gate":   {"label": "Gate",   "color": "red",     "icon": "\u2691"},
    "life":   {"label": "Life",   "color": "green",   "icon": "\u2726"},
    "exam":   {"label": "Exam",   "color": "red",     "icon": "\u2691"},
}

# Fallback day-type colors for the UI.
DEFAULT_DAY_TYPE_COLORS = {
    "FEST":    "orange3",
    "EXAM":    "red",
    "SAT":     "medium_purple",
    "SUN":     "deep_sky_blue4",
    "HOL":     "green",
    "COLLEGE": "deep_sky_blue3",
}

WEEKDAY_KEYS = [
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
]

DAY_ABBREVS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Task types that are daily habits: never carried over to the next week.
HABIT_TYPES = {"anki", "log"}

# Task types excluded from progress percentages (exercises etc.).
PROGRESS_EXCLUDED_TYPES = {"life"}


def empty_plan(name: str = "My Plan") -> dict:
    """A minimal, valid, empty plan skeleton."""
    return {
        "version": "1.0",
        "name": name,
        "total_weeks": 0,
        "start_date": "",
        "current_week": "W1",
        "day_types": {},
        "festival_dates": {},
        "default_day_types_w1_w5": {},
        "default_day_types_college": {},
        "task_type_meta": dict(DEFAULT_TASK_TYPE_META),
        "weekly_scorecard": [],
        "daily_log_fields": [],
        "date_overrides": {},
        "weeks": {},
    }


def empty_week(week_no: int, start_date: str, end_date: str) -> dict:
    """A minimal, valid, empty week skeleton."""
    return {
        "label": "W" + str(week_no),
        "phase": "",
        "ship_target": "",
        "start_date": start_date,
        "end_date": end_date,
        "tasks": [],
        "logs": {},
    }
