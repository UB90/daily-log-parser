"""Plan helpers: task CRUD, day-type resolution, progress, carry-over.

Pure functions over the plan dict - no dates, tasks, or festivals are
hardcoded here. Everything comes from the plan file itself.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional, Tuple

from . import week_generator as wg
from .routine import (
    DAY_ABBREVS,
    HABIT_TYPES,
    PROGRESS_EXCLUDED_TYPES,
)


# ---------------------------------------------------------------- tasks

def find_task(plan: dict, task_id: str) -> Optional[dict]:
    """Find a task anywhere in the plan by its id (case-insensitive)."""
    needle = str(task_id).strip().lower()
    for week in plan.get("weeks", {}).values():
        for task in week.get("tasks", []):
            if str(task.get("id", "")).lower() == needle:
                return task
    return None


def task_ids(plan: dict) -> set:
    return {
        str(t.get("id", "")).lower()
        for w in plan.get("weeks", {}).values()
        for t in w.get("tasks", [])
    }


def next_task_id(plan: dict, week: str, day_abbrev: str) -> str:
    """w1-mon-1, w1-mon-2, ... next free index for that (week, day)."""
    base = week.lower().replace("w", "")
    prefix = "w" + base + "-" + day_abbrev.lower() + "-"
    used = set()
    for task in plan.get("weeks", {}).get(week, {}).get("tasks", []):
        tid = str(task.get("id", ""))
        if tid.lower().startswith(prefix):
            tail = tid[len(prefix):]
            if tail.isdigit():
                used.add(int(tail))
    n = 1
    while n in used:
        n += 1
    return prefix + str(n)


def set_task_done(plan: dict, task_id: str, done: bool) -> dict:
    task = find_task(plan, task_id)
    if task is None:
        raise ValueError("No task with id '" + str(task_id) + "'")
    task["done"] = bool(done)
    return task


def add_task(
    plan: dict,
    week: str,
    text: str,
    day_abbrev: str,
    task_type: str = "ship",
    carried_over_from: Optional[str] = None,
) -> dict:
    if week not in plan.get("weeks", {}):
        raise ValueError("No week '" + str(week) + "' in this plan")
    if day_abbrev.lower() not in DAY_ABBREVS:
        raise ValueError("Bad day '" + str(day_abbrev) + "'")
    w = plan["weeks"][week]
    date = date_for_day(plan, week, day_abbrev)
    task = {
        "id": next_task_id(plan, week, day_abbrev),
        "day": day_abbrev.capitalize() if len(day_abbrev) == 3 else day_abbrev,
        "task": text,
        "type": task_type,
        "done": False,
    }
    if date:
        task["date"] = date
    if carried_over_from:
        task["carried_over_from"] = carried_over_from
    w.setdefault("tasks", []).append(task)
    return task


def delete_task(plan: dict, task_id: str) -> dict:
    needle = str(task_id).strip().lower()
    for week in plan.get("weeks", {}).values():
        tasks = week.get("tasks", [])
        for i, task in enumerate(tasks):
            if str(task.get("id", "")).lower() == needle:
                return tasks.pop(i)
    raise ValueError("No task with id '" + str(task_id) + "'")


def date_for_day(plan: dict, week: str, day_abbrev: str) -> Optional[str]:
    """Best-effort date for a (week, day) pair from the week's date range."""
    w = plan.get("weeks", {}).get(week)
    if not w or not w.get("start_date"):
        return None
    try:
        start = wg.parse_date(w["start_date"])
    except ValueError:
        return None
    offset = DAY_ABBREVS.index(day_abbrev.lower())
    return wg.fmt_date(start + dt.timedelta(days=offset))


# ---------------------------------------------------------- day types

def resolve_day_type(plan: dict, date: dt.date, week: str = "") -> Tuple[str, str]:
    """Resolve the day-type for a date. Returns (TYPE, reason).

    Priority:
      1. date_overrides[YYYY-MM-DD]   (manual, always wins)
      2. festival_dates[YYYY-MM-DD]   (plan data)
      3. period defaults: weeks before college_start_week use
         default_day_types_w1_w5, else default_day_types_college
    """
    iso = wg.fmt_date(date)
    overrides = plan.get("date_overrides", {})
    if iso in overrides:
        return str(overrides[iso]), "override"
    festivals = plan.get("festival_dates", {})
    if iso in festivals:
        return "FEST", "festival: " + str(festivals[iso])
    weekday_key = [
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
    ][date.weekday()]
    no = wg.week_number(week) if week else 0
    college_start = plan.get("college_start_week")
    college_no = wg.week_number(college_start) if college_start else 1
    mapping = (
        plan.get("default_day_types_college", {})
        if no >= college_no
        else plan.get("default_day_types_w1_w5", {})
    )
    dtype = mapping.get(weekday_key) or plan.get("default_day_types", {}).get(weekday_key)
    if dtype:
        return str(dtype), "default"
    return "", "none"


def day_type_info(plan: dict, dtype: str) -> dict:
    info = plan.get("day_types", {}).get(dtype)
    return info if isinstance(info, dict) else {}


# ----------------------------------------------------------- progress

def week_tasks(plan: dict, week: str) -> list:
    w = plan.get("weeks", {}).get(week, {})
    return w.get("tasks", [])


def count_progress(tasks: list) -> Tuple[int, int]:
    """(done, total) over tasks that count (habits count, life does not)."""
    total = 0
    done = 0
    for t in tasks:
        if t.get("type") in PROGRESS_EXCLUDED_TYPES:
            continue
        total += 1
        if t.get("done"):
            done += 1
    return done, total


def week_progress(plan: dict, week: str) -> Tuple[int, int]:
    return count_progress(week_tasks(plan, week))


def anki_days(tasks: list) -> int:
    """How many distinct days have the daily task marked done."""
    days = set()
    for t in tasks:
        if t.get("type") == "anki" and t.get("done"):
            days.add(str(t.get("day", "")) + "|" + str(t.get("date", "")))
    return len(days)


def week_logs(plan: dict, week: str) -> dict:
    return plan.get("weeks", {}).get(week, {}).get("logs", {})


def log_stats(logs: dict) -> dict:
    """Aggregate a week's logs: hours, mood avg, bedtime avg, protein days."""
    hours = [lg.get("dw_hours") for lg in logs.values()
             if isinstance(lg.get("dw_hours"), (int, float))]
    moods = [lg.get("mood") for lg in logs.values()
             if isinstance(lg.get("mood"), (int, float))]
    bedtimes = [lg.get("bedtime") for lg in logs.values() if lg.get("bedtime")]
    protein = [lg for lg in logs.values() if lg.get("protein_met")]
    avg_bt = None
    if bedtimes:
        mins = []
        for bt in bedtimes:
            try:
                t = wg.parse_time(bt)
                mins.append(t.hour * 60 + t.minute)
            except ValueError:
                pass
        if mins:
            avg = sum(mins) // len(mins)
            avg_bt = "{:02d}:{:02d}".format(avg // 60, avg % 60)
    return {
        "days_logged": len(logs),
        "dw_hours": sum(hours) if hours else 0.0,
        "mood_avg": (round(sum(moods) / len(moods), 1) if moods else None),
        "bedtime_avg": avg_bt,
        "protein_days": len(protein),
    }


# ----------------------------------------------------------- weeks

def current_week(plan: dict) -> str:
    return plan.get("current_week") or "W1"


def total_weeks(plan: dict) -> int:
    total = plan.get("total_weeks")
    if isinstance(total, (int, float)) and total:
        return int(total)
    return len(plan.get("weeks", {}))


def set_current_week(plan: dict, week: str) -> None:
    no = wg.week_number(week)
    if not 1 <= no <= total_weeks(plan):
        raise ValueError(
            "Week " + str(week) + " is outside this plan (1-" + str(total_weeks(plan)) + ")"
        )
    plan["current_week"] = wg.week_str(no)


def advance_week(plan: dict) -> Optional[str]:
    """Move to the next week. Returns the new week, or None at the end."""
    no = wg.week_number(current_week(plan))
    if no >= total_weeks(plan):
        return None
    plan["current_week"] = wg.week_str(no + 1)
    return plan["current_week"]


def carry_over(plan: dict, from_week: str, to_week: str) -> list:
    """Copy incomplete, non-habit tasks from one week into another.

    Originals stay where they are (history). Copies carry a
    'carried_over_from' tag. Returns the list of copied tasks.
    """
    if from_week not in plan.get("weeks", {}) or to_week not in plan.get("weeks", {}):
        raise ValueError("Week not found: " + from_week + " -> " + to_week)
    moved = []
    for task in plan["weeks"][from_week].get("tasks", []):
        if task.get("done"):
            continue
        if task.get("type") in HABIT_TYPES:
            continue
        day_abbrev = str(task.get("day", "mon")).lower()[:3]
        if day_abbrev not in DAY_ABBREVS:
            day_abbrev = "mon"
        new_task = add_task(
            plan, to_week, str(task.get("task", "")),
            day_abbrev, str(task.get("type", "ship")),
            carried_over_from=from_week,
        )
        moved.append(new_task)
    return moved


def auto_mark_daily_log(plan: dict, week: str, date: dt.date) -> bool:
    """If a log exists for this date, mark the day's 'log' task done."""
    iso = wg.fmt_date(date)
    logs = week_logs(plan, week)
    if iso not in logs:
        return False
    day_abbrev = wg.date_to_day_abbrev(date)
    for task in plan["weeks"].get(week, {}).get("tasks", []):
        if task.get("type") == "log" and str(task.get("day", "")).lower()[:3] == day_abbrev:
            task["done"] = True
            return True
    return False


def parse_log_args(
    dw_hours=None, mood=None, bedtime=None, protein=None
) -> dict:
    """Validate positional log args. Raises ValueError on bad input."""
    entry = {}
    if dw_hours is not None and str(dw_hours).strip() != "":
        try:
            entry["dw_hours"] = round(float(dw_hours), 1)
        except ValueError as exc:
            raise ValueError("DW hours must be a number, e.g. 4.2") from exc
        if not 0 <= entry["dw_hours"] <= 24:
            raise ValueError("DW hours must be between 0 and 24")
    if mood is not None and str(mood).strip() != "":
        try:
            entry["mood"] = int(str(mood).strip())
        except ValueError as exc:
            raise ValueError("Mood must be 1-5") from exc
        if not 1 <= entry["mood"] <= 5:
            raise ValueError("Mood must be 1-5")
    if bedtime is not None and str(bedtime).strip() != "":
        entry["bedtime"] = wg.parse_time(str(bedtime)).strftime("%H:%M")
    if protein is not None and str(protein).strip() != "":
        p = str(protein).strip().lower()
        if p in ("y", "yes", "true", "1"):
            entry["protein_met"] = True
        elif p in ("n", "no", "false", "0"):
            entry["protein_met"] = False
        else:
            raise ValueError("Protein must be y or n")
    return entry
