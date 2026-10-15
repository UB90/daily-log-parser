#!/usr/bin/env python3
"""daily-log CLI: every command lives here.

The code is a pure handler. It reads plan.json, shows things, edits things,
and saves immediately. Zero plan data is hardcoded - anything you see on
screen (tasks, festivals, timetables) comes from the plan file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from typing import List, Optional

from . import __version__ as PKG_VERSION
from . import plan as P
from . import storage as S
from . import week_generator as wg
from .routine import (
    DAY_ABBREVS,
    DEFAULT_DAY_TYPE_COLORS,
    DEFAULT_TASK_TYPE_META,
    empty_plan,
    empty_week,
)
from .week_generator import DAY_FULL

try:  # pretty UI if available, plain text otherwise
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table as RichTable
    from rich.text import Text
    HAS_RICH = True
except ImportError:  # pragma: no cover
    HAS_RICH = False


# ------------------------------------------------------------------ UI

class UI:
    """Tiny renderer: same calls, rich output or plain lines."""

    def __init__(self) -> None:
        self.rich = HAS_RICH
        self.console = Console() if HAS_RICH else None

    # -- primitives ---------------------------------------------------
    def _print(self, obj) -> None:
        if self.rich:
            try:
                self.console.print(obj)
                return
            except Exception:
                self.rich = False
        try:
            sys.stdout.write(obj + "\n")
        except TypeError:
            sys.stdout.write(str(obj) + "\n")

    def text(self, content: str, style: Optional[str] = None):
        if self.rich and style:
            return Text(content, style=style)
        return content

    def line(self, content: str = "", style: Optional[str] = None) -> None:
        if not content:
            self._print("")
            return
        self._print(Text(content, style=style) if (self.rich and style) else content)

    def panel(self, lines, title: Optional[str] = None, style: Optional[str] = None) -> None:
        """lines: plain strings, (text, style) tuples, or lists of segments."""
        if self.rich:
            body = Text()
            for ln in lines:
                if isinstance(ln, tuple) and len(ln) == 2:
                    body.append(str(ln[0]), ln[1] or "white")
                    body.append("\n")
                elif isinstance(ln, list):
                    for seg, st in ln:
                        body.append(seg, st or "white")
                    body.append("\n")
                else:
                    body.append(str(ln) + "\n")
            try:
                self.console.print(Panel(body, title=title, border_style=style))
                return
            except Exception:
                self.rich = False
        if title:
            self._print("-- " + title + " " + "-" * max(1, 48 - len(title)))
        for ln in lines:
            if isinstance(ln, tuple) and len(ln) == 2:
                self._print(str(ln[0]))
            elif isinstance(ln, list):
                self._print("".join(seg for seg, _ in ln))
            else:
                self._print(str(ln))

    def table(self, headers: List[str], rows: List[list]) -> None:
        """rows: list of rows; each cell is (str, style) or str or None."""
        if self.rich:
            t = RichTable(show_header=True, header_style="bold white",
                          box=None, padding=(0, 2, 0, 0))
            for h in headers:
                t.add_column(h)
            for row in rows:
                cells = []
                for cell in row:
                    if cell is None:
                        cells.append("")
                    elif isinstance(cell, tuple):
                        cells.append(Text(cell[0], style=cell[1] or "white"))
                    else:
                        cells.append(str(cell))
                t.add_row(*cells)
            try:
                self.console.print(t)
                return
            except Exception:
                self.rich = False
        widths = [max(len(str(h)), *(len(str(c[0])) if isinstance(c, tuple) else len(str(c if c is not None else ""))
                                      for c in (r[i] for r in rows))) if rows else len(h)
                  for i, h in enumerate(headers)]
        self._print("  ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
        self._print("  ".join("-" * w for w in widths))
        for row in rows:
            cells = [(c[0] if isinstance(c, tuple) else ("" if c is None else str(c)))
                     for c in row]
            self._print("  ".join(c.ljust(w) for c, w in zip(cells, widths)))

    def bar(self, done: int, total: int, width: int = 22) -> str:
        if total <= 0:
            return "[{}] 0/0".format("-" * width)
        filled = max(0, round(width * done / total))
        return "[{}{}] {}/{}".format("#" * filled, "-" * (width - filled), done, total)

    def ok(self, msg: str) -> None:
        self.line(msg, style="green")

    def err(self, msg: str) -> None:
        self.line(msg, style="red")

    def hint(self, msg: str) -> None:
        self.line(msg, style="bright_black")


UI = UI()  # module-level renderer


# ------------------------------------------------------- plan-aware look

def task_meta(plan: dict, ttype: str) -> dict:
    meta = plan.get("task_type_meta", {}).get(ttype)
    if isinstance(meta, dict) and meta.get("icon"):
        return meta
    return DEFAULT_TASK_TYPE_META.get(ttype, {"label": ttype or "task", "color": "white", "icon": "-"})


def dtype_color(plan: dict, dtype: str) -> str:
    info = P.day_type_info(plan, dtype)
    color = info.get("color")
    if color:
        return str(color)
    return DEFAULT_DAY_TYPE_COLORS.get(dtype, "white")


def dtype_name(plan: dict, dtype: str) -> str:
    info = P.day_type_info(plan, dtype)
    return str(info.get("name", dtype))


def week_dict(plan: dict, week: str) -> dict:
    return plan.get("weeks", {}).get(week, {})


def week_label(plan: dict, week: str) -> str:
    w = week_dict(plan, week)
    return str(w.get("label") or week)


def week_topic(plan: dict, week: str) -> str:
    """Label minus its own 'Wn - ' prefix (for headers that show week separately)."""
    label = week_label(plan, week)
    if label.lower().startswith(week.lower()):
        label = label[len(week):].lstrip(" -·")
    return label


def fmt_day(d: dt.date) -> str:
    return d.strftime("%a %d %b %Y")


def task_day_abbrev(task: dict) -> str:
    if task.get("date"):
        try:
            return wg.date_to_day_abbrev(wg.parse_date(str(task["date"])))
        except ValueError:
            pass
    return str(task.get("day", "")).lower()[:3]


def tasks_for_day(w: dict, day_abbrev: str, iso: Optional[str] = None) -> list:
    out = []
    for t in w.get("tasks", []):
        if task_day_abbrev(t) != day_abbrev:
            continue
        if t.get("date") and iso and t["date"] != iso:
            continue
        out.append(t)
    return out


def date_in_week(w: dict, d: dt.date) -> bool:
    try:
        s = wg.parse_date(w["start_date"])
        e = wg.parse_date(w.get("end_date") or w["start_date"])
        return s <= d <= e
    except (KeyError, ValueError):
        return False


def task_line(plan: dict, task: dict) -> list:
    """One rendered task row: checkbox, icon, id, text, tags."""
    meta = task_meta(plan, str(task.get("type", "")))
    if task.get("done"):
        box, box_style = "[x]", "green"
    else:
        box, box_style = "[ ]", "white"
    row = [
        (box + " ", box_style),
        (str(meta.get("icon", "-")) + " ", str(meta.get("color", "white"))),
        (str(task.get("id", "")) + " ", "bright_black"),
        (str(task.get("task", "")), "dim" if task.get("done") else "white"),
    ]
    if task.get("carried_over_from"):
        row.append((" (carried from " + str(task["carried_over_from"]) + ")", "yellow"))
    if task.get("done") and task.get("completed_on"):
        row.append((" done " + str(task["completed_on"]), "bright_black"))
    return row


# ------------------------------------------------------- auto features

def auto_advance(plan: dict, today: Optional[dt.date] = None) -> List[str]:
    """Move current_week to the week containing today, carrying tasks.

    Returns a list of human-readable notices. Caller must save.
    """
    if today is None:
        today = dt.date.today()
    detected = wg.detect_week(plan, today)
    current = wg.week_number(P.current_week(plan))
    notices = []
    while current < detected:
        from_w = wg.week_str(current)
        to_w = wg.week_str(current + 1)
        if from_w in plan.get("weeks", {}) and to_w in plan.get("weeks", {}):
            moved = P.carry_over(plan, from_w, to_w)
            if moved:
                notices.append(
                    "Carried {} unfinished task(s) from {} to {}".format(
                        len(moved), from_w, to_w
                    )
                )
        current += 1
    if detected != wg.week_number(P.current_week(plan)):
        plan["current_week"] = wg.week_str(detected)
        notices.append("Week auto-advanced to " + wg.week_str(detected))
    return notices


# ------------------------------------------------------------ commands

def cmd_init(args) -> int:
    if S.is_initialized() and not args.force:
        UI.err("A plan already exists at " + str(S.plan_path()))
        UI.hint("Use 'daily-log init --force' to overwrite (progress is lost),")
        UI.hint("or 'daily-log plan reset' to start an empty plan.")
        return 1
    if args.plan:
        # Bring your own plan file - the package never bundles one.
        source = os.path.expanduser(str(args.plan))
        if not os.path.isfile(source):
            UI.err("Plan file not found: " + source)
            return 1
        S.copy_plan_file(source, S.plan_path())
    else:
        # No bundled default: build a generic, empty starter in memory.
        # Zero plan data is shipped inside the package.
        today = dt.date.today()
        monday = today - dt.timedelta(days=today.weekday())  # week starts Monday
        starter = empty_plan("My Plan")
        starter["start_date"] = wg.fmt_date(monday)
        starter["total_weeks"] = 1
        starter["current_week"] = "W1"
        starter["weeks"]["W1"] = empty_week(
            1, wg.fmt_date(monday), wg.fmt_date(monday + dt.timedelta(days=6))
        )
        S.save_plan(starter)
    plan = S.load_plan()
    total_tasks = sum(len(w.get("tasks", [])) for w in plan.get("weeks", {}).values())
    UI.panel(
        [
            [("Name:  ", "bold"), (str(plan.get("name", "My Plan")), "white")],
            [("Weeks: ", "bold"), (str(P.total_weeks(plan)), "white")],
            [("Tasks: ", "bold"), (str(total_tasks), "white")],
            [("Start: ", "bold"), (str(plan.get("start_date", "?")), "white")],
            [("Now:   ", "bold"), ("week " + P.current_week(plan), "cyan")],
            [("", None)],
            [("File:  ", "bold"), (str(S.plan_path()), "bright_black")],
            [("", None)],
            "Tomorrow morning, just run:",
            [("   daily-log today", "green")],
        ],
        title="Plan initialized",
        style="green",
    )
    if not args.plan:
        UI.hint("This is an empty starter plan - it contains no data.")
        UI.hint("Add a task:       daily-log add \"Read 20 pages\" --type learn")
        UI.hint("Load a plan file: daily-log init --force --plan <your-plan.json>")
    else:
        UI.hint("Show tasks: daily-log week   |   Log the day: daily-log log 4.2 4")
    return 0


def cmd_today(args) -> int:
    plan = S.require_plan()
    notices = auto_advance(plan)
    if notices:
        S.save_plan(plan)
        for n in notices:
            UI.line(n, style="yellow")
    today = dt.date.today()
    week = P.current_week(plan)
    w = week_dict(plan, week)
    dtype, reason = P.resolve_day_type(plan, today, week)
    iso = wg.fmt_date(today) if date_in_week(w, today) else None
    day_abbrev = wg.date_to_day_abbrev(today)

    header = [
        (fmt_day(today), "bold white"),
        ("   ", None),
        (week + " - " + week_topic(plan, week), "cyan"),
    ]
    if dtype:
        header.append(("   [" + dtype + "] ", dtype_color(plan, dtype)))
        header.append((dtype_name(plan, dtype), dtype_color(plan, dtype)))
    UI.panel([header], style=dtype_color(plan, dtype) or "white")
    if reason.startswith("festival"):
        UI.line("Festival: " + reason.split("festival:", 1)[1].strip(), style="orange3")
    if not date_in_week(w, today):
        if today < wg.parse_date(w.get("start_date", "2000-01-01")):
            UI.line("Note: this plan starts on " + str(w.get("start_date")), style="yellow")
        elif w.get("end_date") and today > wg.parse_date(w["end_date"]):
            UI.line("Note: the last week of this plan ended " + str(w["end_date"]), style="yellow")

    info = P.day_type_info(plan, dtype)
    if info.get("schedule"):
        UI.line("Timetable (" + dtype + "):", style="bold")
        for block in info["schedule"]:
            when, what = str(block[0]), str(block[1])
            UI.line("  " + when.ljust(14) + " " + what, style="white")
        UI.line("")

    tasks = tasks_for_day(w, day_abbrev, iso)
    if tasks:
        UI.line("Tasks for " + DAY_FULL[day_abbrev] + ":", style="bold")
        for t in tasks:
            print_task_row(plan, t)
        done, total = P.count_progress(tasks)
        UI.line("")
        UI.line("Today: " + UI.bar(done, total), style="cyan")
    else:
        UI.line("No tasks planned for today.", style="yellow")
    logs = P.week_logs(plan, week)
    if iso in logs:
        lg = logs[iso]
        UI.hint("Logged: {}h DW, mood {}/5, bed {}".format(
            lg.get("dw_hours", "-"), lg.get("mood", "-"), lg.get("bedtime", "-")))
        UI.hint("Log the day:  daily-log log 4.2 4 22:30 y")
    else:
        UI.hint("Log the day:  daily-log log 4.2 4 22:30 y")
    UI.hint("Mark done:    daily-log mark <task-id>")
    return 0


def cmd_week(args) -> int:
    plan = S.require_plan()
    if args.week:
        try:
            week = wg.week_str(wg.week_number(args.week))
        except ValueError as e:
            UI.err(str(e)); return 1
    else:
        week = P.current_week(plan)
    if week not in plan.get("weeks", {}):
        UI.err("Week " + week + " is not in this plan (1-" + str(P.total_weeks(plan)) + ")")
        return 1
    w = week_dict(plan, week)
    is_current = week == P.current_week(plan)
    title = week + (" (current)" if is_current else "") + "  " + week_topic(plan, week)
    phase = w.get("phase") or w.get("ship_target") or ""
    UI.panel([
        [(title, "bold white")],
        [(str(w.get("start_date", "?")) + " to " + str(w.get("end_date", "?")), "bright_black")],
        *([[(phase, "cyan")]] if phase else []),
    ], style="cyan")
    today_iso = wg.fmt_date(dt.date.today())
    for day_abbrev in DAY_ABBREVS:
        d = None
        if w.get("start_date"):
            try:
                base = wg.parse_date(w["start_date"])
                d = base + dt.timedelta(days=DAY_ABBREVS.index(day_abbrev))
            except ValueError:
                d = None
        iso = wg.fmt_date(d) if d else None
        dtype, _ = P.resolve_day_type(plan, d, week) if d else ("", "")
        marker = "  <- today" if (iso == today_iso and is_current) else ""
        head = DAY_FULL[day_abbrev] + (("  " + iso) if iso else "")
        line = [(head, "bold " + (dtype_color(plan, dtype) or "white"))]
        if dtype:
            line.append((" [" + dtype + "]", dtype_color(plan, dtype)))
        if marker:
            line.append((marker, "green bold"))
        print_line(line)
        tasks = tasks_for_day(w, day_abbrev, None)
        if not tasks:
            UI.line("    -", style="bright_black")
        for t in tasks:
            print_task_row(plan, t, "    ")
    done, total = P.week_progress(plan, week)
    carried = sum(1 for t in w.get("tasks", []) if t.get("carried_over_from"))
    UI.line("")
    UI.line("Week progress: " + UI.bar(done, total), style="cyan")
    if carried:
        UI.line(str(carried) + " task(s) were carried into this week from earlier.", style="yellow")
    UI.hint("Mark a task: daily-log mark <id>    Log a day: daily-log log <hours>")
    return 0


def print_line(segments) -> None:
    """Print one row of (text, style) segments."""
    if UI.rich:
        txt = Text()
        for seg, st in segments:
            txt.append(seg, st or "white")
        UI._print(txt)
    else:
        UI.line("".join(seg for seg, _ in segments))


def print_task_row(plan: dict, task: dict, indent: str = "") -> None:
    rows = task_line(plan, task)
    if UI.rich:
        txt = Text()
        for i, (seg, st) in enumerate(rows):
            txt.append((indent if i == 0 else "") + seg, st or "white")
        UI._print(txt)
    else:
        UI.line(indent + "".join(seg for seg, _ in rows))


# ---------------------------------------------------- mark / add tasks

def cmd_mark(args) -> int:
    plan = S.require_plan()
    try:
        task = P.set_task_done(plan, args.task_id, True)
        task["completed_on"] = wg.fmt_date(dt.date.today())
    except ValueError as e:
        UI.err(str(e)); return 1
    S.save_plan(plan)
    UI.ok("Done: [" + str(task.get("id")) + "] " + str(task.get("task")))
    return 0


def cmd_unmark(args) -> int:
    plan = S.require_plan()
    try:
        task = P.set_task_done(plan, args.task_id, False)
        task.pop("completed_on", None)
    except ValueError as e:
        UI.err(str(e)); return 1
    S.save_plan(plan)
    UI.ok("Unmarked: [" + str(task.get("id")) + "] " + str(task.get("task")))
    return 0


def cmd_toggle(args) -> int:
    plan = S.require_plan()
    try:
        task = P.find_task(plan, args.task_id)
        if task is None:
            raise ValueError("No task with id '" + str(args.task_id) + "'")
        task["done"] = not task.get("done")
        if task["done"]:
            task["completed_on"] = wg.fmt_date(dt.date.today())
        else:
            task.pop("completed_on", None)
    except ValueError as e:
        UI.err(str(e)); return 1
    S.save_plan(plan)
    state = "Done" if task["done"] else "Back to open"
    UI.ok(state + ": [" + str(task.get("id")) + "] " + str(task.get("task")))
    return 0


def cmd_add(args) -> int:
    plan = S.require_plan()
    week = P.current_week(plan)
    day = (args.day or "").strip().lower()
    if not day:
        today = dt.date.today()
        day = wg.date_to_day_abbrev(today)
    if day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        pass
    elif day[:3] in DAY_ABBREVS:
        day = day[:3]
    else:
        UI.err("Bad day '" + str(args.day) + "' - use Mon, Tue, ... Sun")
        return 1
    ttype = (args.type or "ship").strip().lower()
    known = set(plan.get("task_type_meta", {}).keys()) | set(DEFAULT_TASK_TYPE_META.keys())
    if ttype not in known:
        UI.err("Unknown task type '" + ttype + "'.")
        UI.hint("Known types: " + ", ".join(sorted(known)))
        return 1
    try:
        task = P.add_task(plan, week, args.text, day, ttype)
    except ValueError as e:
        UI.err(str(e)); return 1
    S.save_plan(plan)
    UI.ok("Added [" + str(task["id"]) + "] to " + week + " " + str(task.get("day")))
    UI.hint(str(task.get("date", "")) + "  " + str(task.get("task")))
    return 0


def cmd_delete(args) -> int:
    plan = S.require_plan()
    try:
        task = P.delete_task(plan, args.task_id)
    except ValueError as e:
        UI.err(str(e)); return 1
    S.save_plan(plan)
    UI.ok("Deleted [" + str(task.get("id")) + "] " + str(task.get("task")))
    return 0


# ------------------------------------------------------------ daily log

def cmd_log(args) -> int:
    plan = S.require_plan()
    today = dt.date.today()
    week = wg.week_str(wg.detect_week(plan, today))
    if week not in plan.get("weeks", {}):
        week = P.current_week(plan)
    iso = wg.fmt_date(today)
    w = week_dict(plan, week)

    fields = [("dw_hours", "DW hours (e.g. 4.2)"),
              ("mood", "Mood 1-5"),
              ("bedtime", "Bedtime HH:MM"),
              ("protein", "Protein met? y/n")]

    provided = [args.dw_hours, args.mood, args.bedtime, args.protein]
    if all(p is None or str(p).strip() == "" for p in provided):
        if not sys.stdin.isatty():
            UI.err("No values given. Usage: daily-log log <dw_hours> <mood> <bedtime> <protein>")
            return 1
        UI.line("Daily log for " + fmt_day(today) + " - press Enter to keep each default", style="bold")
        values = {}
        existing = w.get("logs", {}).get(iso, {})
        for key, label in fields:
            default = existing.get(key, "")
            for _ in range(3):
                raw = input("  " + label + (" [" + str(default) + "]" if default != "" else "") + ": ").strip()
                if raw == "":
                    if default != "":
                        values[key] = default
                    break
                try:
                    entry = P.parse_log_args(**{key: raw})
                    values.update(entry)
                    break
                except ValueError as e:
                    UI.err(str(e))
            else:
                UI.err("Too many bad attempts for " + key + " - skipped")
        try:
            entry = values
            if not entry:
                UI.hint("Nothing to save.")
                return 0
        except ValueError as e:
            UI.err(str(e)); return 1
    else:
        try:
            entry = P.parse_log_args(args.dw_hours, args.mood, args.bedtime, args.protein)
        except ValueError as e:
            UI.err(str(e))
            UI.hint("Order: dw_hours mood bedtime protein   e.g.  daily-log log 4.2 4 22:30 y")
            return 1

    logs = w.setdefault("logs", {})
    logs.setdefault(iso, {}).update(entry)
    P.auto_mark_daily_log(plan, week, today)
    S.save_plan(plan)
    saved = logs[iso]
    UI.ok("Logged " + iso + " (" + week + "): " + "  ".join(
        k + "=" + str(v) for k, v in saved.items()))
    return 0


def cmd_sync(args) -> int:
    plan = S.require_plan()
    today = dt.date.today()
    notices = auto_advance(plan)
    marked = P.auto_mark_daily_log(plan, P.current_week(plan), today)
    if notices or marked:
        S.save_plan(plan)
    for n in notices:
        UI.line(n, style="yellow")
    if marked:
        UI.ok("Daily-log task auto-marked for today (a log exists).")
    if not notices and not marked:
        UI.ok("Everything already in sync - you are in " + P.current_week(plan) + ".")
    return 0


# --------------------------------------------------------- done / summary

def cmd_done(args) -> int:
    plan = S.require_plan()
    week = P.current_week(plan)
    w = week_dict(plan, week)
    done, total = P.week_progress(plan, week)
    stats = P.log_stats(P.week_logs(plan, week))
    next_no = wg.week_number(week) + 1

    if next_no > P.total_weeks(plan):
        UI.panel([
            [("PLAN COMPLETE", "bold green")],
            [("", None)],
            "You reached the end of " + str(plan.get("name", "the plan")) + ".",
            "Final week " + week + ": " + UI.bar(done, total),
            [("", None)],
            "Export a keepsake:  daily-log export final-plan.json",
        ], title="Finish line", style="green")
        return 0

    to_w = wg.week_str(next_no)
    moved = P.carry_over(plan, week, to_w)
    plan["current_week"] = to_w
    S.save_plan(plan)
    lines = [
        [("Week " + week + " closed.", "bold white")],
        [("Tasks:  ", None), (UI.bar(done, total), "cyan")],
        [("Logged: ", None), ("{}h DW over {} day(s)".format(
            stats["dw_hours"], stats["days_logged"]), "white")],
        [("", None)],
        ("You are now in " + to_w + " - " + week_topic(plan, to_w), None),
    ]
    if moved:
        lines.append([("Carried over: ", "yellow"), (str(len(moved)) + " unfinished task(s)", "yellow")])
        lines.append(("They keep a 'carried over from' tag so you can spot them.", None))
    else:
        lines.append(("Nothing to carry over - clean week!", None))
    UI.panel(lines, title="Week " + week + " summary", style="green")
    UI.hint("Start the new week:  daily-log today")
    return 0


def cmd_summary(args) -> int:
    plan = S.require_plan()
    if args.week:
        try:
            week = wg.week_str(wg.week_number(args.week))
        except ValueError as e:
            UI.err(str(e)); return 1
    else:
        week = P.current_week(plan)
    if week not in plan.get("weeks", {}):
        UI.err("Week " + week + " is not in this plan (1-" + str(P.total_weeks(plan)) + ")")
        return 1
    w = week_dict(plan, week)
    tasks = w.get("tasks", [])
    done, total = P.count_progress(tasks)
    stats = P.log_stats(P.week_logs(plan, week))
    carried = [t for t in tasks if t.get("carried_over_from")]

    lines = [
        [(week + "  " + week_topic(plan, week), "bold white")],
        [(str(w.get("start_date", "?")) + " to " + str(w.get("end_date", "?")), "bright_black")],
    ]
    if w.get("phase"):
        lines.append([(str(w["phase"]), "cyan")])
    if w.get("ship_target"):
        lines.append([("Ship target: ", "bold"), (str(w["ship_target"]), "white")])
    lines += [
        [("", None)],
        [("Tasks done:    ", "bold"), (UI.bar(done, total), "cyan")],
        [("Anki days:     ", "bold"), (str(P.anki_days(tasks)) + " / 7", "magenta")],
        [("DW logged:     ", "bold"),
         (str(stats["dw_hours"]) + " h over " + str(stats["days_logged"]) + " day(s)", "white")],
        [("Mood average:  ", "bold"), (str(stats["mood_avg"] if stats["mood_avg"] else "-") + " / 5", "white")],
        [("Bedtime avg:   ", "bold"), (stats["bedtime_avg"] or "-", "white")],
        [("Protein days:  ", "bold"), (str(stats["protein_days"]), "white")],
    ]
    if carried:
        lines.append([("Carried into this week: ", "yellow"), (str(len(carried)), "yellow")])
        for t in carried[:6]:
            lines.append(("  - [" + str(t.get("id")) + "] " + str(t.get("task")), None))
        if len(carried) > 6:
            lines.append(("  ... and " + str(len(carried) - 6) + " more", None))
    gates = [t for t in tasks if t.get("type") == "gate"]
    for g in gates:
        lines.append([("GATE: ", "red bold"), (str(g.get("task")), "red")])
        lines.append([("       " + ("PASSED" if g.get("done") else "not passed yet"), "red" if not g.get("done") else "green")])
    UI.panel(lines, title="Weekly summary", style="cyan")

    logs = P.week_logs(plan, week)
    if logs:
        UI.line("")
        UI.line("Daily logs:", style="bold")
        rows = []
        for iso in sorted(logs.keys()):
            lg = logs[iso]
            rows.append([iso,
                         (str(lg.get("dw_hours", "-")), None),
                         (str(lg.get("mood", "-")), None),
                         (str(lg.get("bedtime", "-")), None),
                         ("y" if lg.get("protein_met") else "n", None)])
        UI.table(["date", "DW h", "mood", "bed", "protein"], rows)
    UI.hint("Close the week when it ends:  daily-log done")
    return 0


# ------------------------------------------------------- week management

def cmd_set_day(args) -> int:
    plan = S.require_plan()
    values = list(args.values or [])
    known = set(plan.get("day_types", {}).keys())
    if args.date:
        if len(values) != 1:
            UI.err("Usage: daily-log set-day --date YYYY-MM-DD <TYPE>")
            return 1
        try:
            d = wg.parse_date(args.date)
        except ValueError as e:
            UI.err(str(e)); return 1
        dtype = values[0].strip().upper()
        if known and dtype not in known:
            UI.err("Unknown day type '" + dtype + "'. Known: " + ", ".join(sorted(known)))
            return 1
        plan.setdefault("date_overrides", {})[wg.fmt_date(d)] = dtype
        S.save_plan(plan)
        UI.ok(wg.fmt_date(d) + " -> " + dtype + " (date override saved)")
        return 0
    if len(values) != 2:
        UI.err("Usage: daily-log set-day <Mon..Sun> <TYPE>")
        UI.err("    or daily-log set-day --date YYYY-MM-DD <TYPE>")
        return 1
    weekday, dtype = values[0].lower(), values[1].strip().upper()
    if weekday not in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        UI.err("Bad weekday '" + values[0] + "' - spell it out, e.g. monday")
        return 1
    if known and dtype not in known:
        UI.err("Unknown day type '" + dtype + "'. Known: " + ", ".join(sorted(known)))
        return 1
    current_no = wg.week_number(P.current_week(plan))
    college_start = plan.get("college_start_week")
    college_no = wg.week_number(college_start) if college_start else 1
    if current_no < college_no:
        plan.setdefault("default_day_types_w1_w5", {})[weekday] = dtype
        scope = "weeks before " + str(college_start)
    else:
        plan.setdefault("default_day_types_college", {})[weekday] = dtype
        scope = "weeks from " + str(college_start) + " on"
    S.save_plan(plan)
    UI.ok(weekday + " -> " + dtype + " (saved; applies to " + scope + ")")
    return 0


def cmd_set_week(args) -> int:
    plan = S.require_plan()
    try:
        P.set_current_week(plan, args.week)
    except ValueError as e:
        UI.err(str(e)); return 1
    S.save_plan(plan)
    UI.ok("Current week is now " + P.current_week(plan) + " - " +
          week_label(plan, P.current_week(plan)))
    return 0


def cmd_carryover(args) -> int:
    plan = S.require_plan()
    from_w = args.from_week or P.current_week(plan)
    try:
        from_no = wg.week_number(from_w)
    except ValueError as e:
        UI.err(str(e)); return 1
    to_no = wg.week_number(args.to_week) if args.to_week else from_no + 1
    to_w = wg.week_str(to_no)
    if from_w not in plan.get("weeks", {}) or to_w not in plan.get("weeks", {}):
        UI.err("Weeks must exist in the plan (1-" + str(P.total_weeks(plan)) + ")")
        return 1
    pending = [t for t in week_dict(plan, from_w).get("tasks", [])
               if not t.get("done") and t.get("type") not in ("anki", "log")]
    if args.dry_run:
        UI.line("DRY RUN - " + str(len(pending)) + " task(s) would move " + from_w + " -> " + to_w, style="yellow")
        for t in pending:
            UI.hint("  - [" + str(t.get("id")) + "] " + str(t.get("task")))
        return 0
    try:
        moved = P.carry_over(plan, from_w, to_w)
    except ValueError as e:
        UI.err(str(e)); return 1
    S.save_plan(plan)
    UI.ok("Carried " + str(len(moved)) + " task(s) " + from_w + " -> " + to_w)
    for t in moved[:8]:
        UI.hint("  - [" + str(t.get("id")) + "] " + str(t.get("task")))
    if len(moved) > 8:
        UI.hint("  ... and " + str(len(moved) - 8) + " more")
    return 0


# ---------------------------------------------------------- plan commands

def cmd_plan(args) -> int:
    plan = S.require_plan()
    sub = args.plan_cmd
    if sub == "show":
        total_tasks = sum(len(w.get("tasks", [])) for w in plan.get("weeks", {}).values())
        done_tasks = sum(1 for w in plan.get("weeks", {}).values()
                         for t in w.get("tasks", []) if t.get("done"))
        lines = [
            [("Name:     ", "bold"), (str(plan.get("name", "?")), "white")],
            [("Version:  ", "bold"), (str(plan.get("version", "?")), "white")],
            [("Weeks:    ", "bold"), (str(P.total_weeks(plan)), "white")],
            [("Current:  ", "bold"), (P.current_week(plan) + " - " + week_topic(plan, P.current_week(plan)), "cyan")],
            [("Start:    ", "bold"), (str(plan.get("start_date", "?")), "white")],
            [("Tasks:    ", "bold"), (str(done_tasks) + " done / " + str(total_tasks) + " total", "white")],
            [("Day types:", "bold"), (" " + ", ".join(sorted(plan.get("day_types", {}).keys())) or " none", "white")],
            [("Festivals:", "bold"), (str(len(plan.get("festival_dates", {}))) + " dates", "white")],
            [("File:     ", "bold"), (str(S.plan_path()), "bright_black")],
        ]
        UI.panel(lines, title="Plan", style="cyan")
        return 0
    if sub == "path":
        UI.line(str(S.plan_path()))
        return 0
    if sub == "edit":
        editor = os.environ.get("EDITOR", "vi")
        rc = subprocess.call([editor, str(S.plan_path())])
        if rc != 0:
            UI.err("Editor exited with code " + str(rc))
            return 1
        S.load_plan()  # validate it still parses
        UI.ok("Plan file re-loaded and valid.")
        return 0
    if sub == "reset":
        if not args.yes:
            try:
                if sys.stdin.isatty():
                    ans = input("This deletes all progress. Type y to confirm: ").strip().lower()
                else:
                    ans = ""
            except EOFError:
                ans = ""
            if ans not in ("y", "yes"):
                UI.hint("Reset cancelled (use --yes to skip this question).")
                return 0
        blank = empty_plan(str(plan.get("name", "My Plan")))
        S.save_plan(blank)
        UI.ok("Plan reset to an empty skeleton.")
        UI.hint("Bring a real plan back:  daily-log init --force --plan <your-plan.json>")
        return 0
    if sub == "export":
        S.copy_plan_file(S.plan_path(), os.path.expanduser(args.path))
        UI.ok("Exported to " + str(args.path))
        return 0
    if sub == "import":
        S.copy_plan_file(os.path.expanduser(args.path), S.plan_path())
        S.load_plan()  # validate
        plan = S.load_plan()
        UI.ok("Imported plan: " + str(plan.get("name", "?")) + " (" +
              str(P.total_weeks(plan)) + " weeks)")
        return 0
    return 1


def cmd_export(args) -> int:
    S.require_plan()
    S.copy_plan_file(S.plan_path(), os.path.expanduser(args.path))
    UI.ok("Backup written to " + str(args.path))
    return 0


def cmd_import(args) -> int:
    S.copy_plan_file(os.path.expanduser(args.path), S.plan_path())
    plan = S.load_plan()
    UI.ok("Restored plan: " + str(plan.get("name", "?")) + " (" +
          str(P.total_weeks(plan)) + " weeks) - all progress preserved")
    return 0


# ------------------------------------------------------------- listings

def cmd_list_weeks(args) -> int:
    plan = S.require_plan()
    current = P.current_week(plan)
    rows = []
    for no in range(1, P.total_weeks(plan) + 1):
        week = wg.week_str(no)
        w = week_dict(plan, week)
        done, total = P.count_progress(w.get("tasks", []))
        label = week_label(plan, week)
        rows.append([
            (week, "cyan bold" if week == current else None),
            (str(w.get("start_date", "?")), None),
            (str(w.get("end_date", "?")), None),
            (label, None),
            (("{}/{}".format(done, total)), "green" if total and done == total else None),
            ("=> you are here" if week == current else "", "green bold" if week == current else None),
        ])
    UI.line("Plan: " + str(plan.get("name", "?")) + " - " + str(P.total_weeks(plan)) + " weeks", style="bold")
    UI.table(["week", "start", "end", "label", "tasks", ""], rows)
    return 0


def cmd_list_day_types(args) -> int:
    plan = S.require_plan()
    rows = []
    for dtype, info in plan.get("day_types", {}).items():
        if not isinstance(info, dict):
            continue
        rows.append([
            (dtype, dtype_color(plan, dtype)),
            (str(info.get("name", "")), None),
            (str(info.get("wake", "-")), None),
            (str(info.get("dw_hours", "-")), None),
            (str(info.get("exercise", "-")), None),
        ])
    if not rows:
        UI.hint("No day types defined in this plan.")
        return 0
    UI.line("Day types in this plan:", style="bold")
    UI.table(["type", "name", "wake", "DW h", "exercise"], rows)
    UI.hint("See one timetable:  daily-log show-day <TYPE>")
    return 0


def cmd_show_day(args) -> int:
    plan = S.require_plan()
    dtype = args.day_type.strip().upper()
    info = P.day_type_info(plan, dtype)
    if not info:
        UI.err("No day type '" + dtype + "' in this plan.")
        UI.hint("List them:  daily-log list-day-types")
        return 1
    lines = [
        [(dtype + " - " + str(info.get("name", "")), "bold " + dtype_color(plan, dtype))],
        [("wake: ", "bold"), (str(info.get("wake", "-")), None)],
        [("deep-work target: ", "bold"), (str(info.get("dw_hours", "-")) + " h", None)],
        [("exercise: ", "bold"), (str(info.get("exercise", "-")), None)],
    ]
    if info.get("schedule"):
        lines.append([("", None)])
        lines.append(("Timetable:", "bold"))
        for block in info["schedule"]:
            lines.append(("  " + str(block[0]).ljust(14) + " " + str(block[1]), None))
    UI.panel(lines, title="Day type", style=dtype_color(plan, dtype))
    return 0


# ---------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="daily-log",
        description="One-file, file-driven, offline plan tracker.",
        epilog="Morning: daily-log today | Night: daily-log log 4.2 4 22:30 y",
    )
    p.add_argument("--version", action="version",
                   version="daily-log " + PKG_VERSION)
    sub = p.add_subparsers(dest="cmd", metavar="<command>")

    sp = sub.add_parser("init", help="initialize ~/.daily-log/plan.json")
    sp.add_argument("--plan", help="path to a plan JSON file")
    sp.add_argument("--force", action="store_true", help="overwrite an existing plan")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("today", help="show today's tasks + timetable")
    sp.set_defaults(func=cmd_today)

    sp = sub.add_parser("week", help="this week's tasks by day")
    sp.add_argument("--week", help="e.g. W3")
    sp.set_defaults(func=cmd_week)

    sp = sub.add_parser("mark", help="mark a task done")
    sp.add_argument("task_id")
    sp.set_defaults(func=cmd_mark)

    sp = sub.add_parser("unmark", help="mark a task not done")
    sp.add_argument("task_id")
    sp.set_defaults(func=cmd_unmark)

    sp = sub.add_parser("toggle", help="flip done / not done")
    sp.add_argument("task_id")
    sp.set_defaults(func=cmd_toggle)

    sp = sub.add_parser("add", help="add a custom task")
    sp.add_argument("text")
    sp.add_argument("--day", help="Mon, Tue, ... (default: today)")
    sp.add_argument("--type", default="ship", help="task type (default: ship)")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("delete", help="delete a custom task")
    sp.add_argument("task_id")
    sp.set_defaults(func=cmd_delete)

    sp = sub.add_parser("log", help="daily log: dw_hours [mood] [bedtime] [protein]")
    sp.add_argument("dw_hours", nargs="?", default=None)
    sp.add_argument("mood", nargs="?", default=None)
    sp.add_argument("bedtime", nargs="?", default=None)
    sp.add_argument("protein", nargs="?", default=None)
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("sync", help="auto-detect week, advance, auto-mark")
    sp.set_defaults(func=cmd_sync)

    sp = sub.add_parser("done", help="finish the week, advance (carries incomplete)")
    sp.set_defaults(func=cmd_done)

    sp = sub.add_parser("summary", help="weekly summary")
    sp.add_argument("--week", help="e.g. W3")
    sp.set_defaults(func=cmd_summary)

    sp = sub.add_parser("set-day", help="override a day-type")
    sp.add_argument("values", nargs="*", help="<Mon..Sun> <TYPE>  or  <TYPE> with --date")
    sp.add_argument("--date", help="YYYY-MM-DD for a specific date")
    sp.set_defaults(func=cmd_set_day)

    sp = sub.add_parser("set-week", help="jump to a week")
    sp.add_argument("week")
    sp.set_defaults(func=cmd_set_week)

    sp = sub.add_parser("carryover", help="carry incomplete tasks to next week")
    sp.add_argument("from_week", nargs="?", default=None)
    sp.add_argument("to_week", nargs="?", default=None)
    sp.add_argument("--dry-run", action="store_true", dest="dry_run")
    sp.set_defaults(func=cmd_carryover)

    sp = sub.add_parser("plan", help="plan file commands")
    psub = sp.add_subparsers(dest="plan_cmd", metavar="<subcommand>")
    psub.add_parser("show", help="show plan summary")
    psub.add_parser("edit", help="open in $EDITOR")
    psub.add_parser("path", help="print file path")
    sp_reset = psub.add_parser("reset", help="reset to empty plan")
    sp_reset.add_argument("--yes", action="store_true", help="skip confirmation")
    sp_exp = psub.add_parser("export", help="export plan to a file")
    sp_exp.add_argument("path")
    sp_imp = psub.add_parser("import", help="import a plan from a file")
    sp_imp.add_argument("path")
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("export", help="backup plan file")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("import", help="restore from backup")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("list-weeks", help="list all weeks")
    sp.set_defaults(func=cmd_list_weeks)

    sp = sub.add_parser("list-day-types", help="list day types")
    sp.set_defaults(func=cmd_list_day_types)

    sp = sub.add_parser("show-day", help="show a day-type timetable")
    sp.add_argument("day_type")
    sp.set_defaults(func=cmd_show_day)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        UI.hint("\nFastest start:  daily-log today")
        return 0
    if getattr(args, "cmd", None) == "plan" and not getattr(args, "plan_cmd", None):
        parser.parse_args(["plan", "--help"])
        return 0
    try:
        return args.func(args)
    except ValueError as e:
        UI.err(str(e))
        return 1
    except KeyboardInterrupt:
        UI.err("Interrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
