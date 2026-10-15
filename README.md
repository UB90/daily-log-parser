# daily-log-parser

A  CLI plan tracker. **One file. File-driven. Offline.**

All plan data (tasks, day-types, festivals, timetables) lives in a single JSON
file of **yours**. The code is a pure handler — it reads the file, modifies
it, saves it.

```
~/.daily-log/
└── plan.json    ← EVERYTHING: tasks + done state + logs + overrides
```

# Install

Requires Python 3.10+.

```bash
tar -xzf daily-log-parser.tar.gz
cd daily-log-parser

# option A: uv (recommended)
uv tool install .

# option B: pip
pip install .
```

Set `DAILY_LOG_DIR` to store the plan somewhere other than `~/.daily-log`.

## Get started

```bash
# Option 1: load your own plan file (recommended)
daily-log init --plan /path/to/your-plan.json

# Option 2: try the generic 4-week demo plan shipped in plans/
daily-log init --plan plans/example-plan.json

# Option 3: start from an empty starter (no data at all)
daily-log init
```

The repo ships exactly one plan file: `plans/example-plan.json` — a clearly
generic 4-week demo (WORK/OFF day-types, placeholder tasks) so newcomers can
try the tool. Your real plan stays out of the repo.

## Daily workflow

```bash
# Morning
daily-log today

# Mark a task done (saves to plan.json immediately)
daily-log mark w1-wed-1

# Easy flip done/not-done
daily-log toggle w1-wed-1

# End of day — just type 2 numbers
daily-log log 4.2 4

# Weekly review
daily-log summary
daily-log done                    # advance to next week
```

## All commands

| Command                                                 | What it does                                      | Saves to file? |
| ------------------------------------------------------- | ------------------------------------------------- | -------------- |
| `daily-log init [--plan <path>] [--force]`            | Initialize (your plan file, or empty starter)     | ✓             |
| `daily-log today`                                     | Show today's tasks + timetable                    | —             |
| `daily-log week [--week W1]`                          | This week's tasks by day                          | —             |
| `daily-log mark <task-id>`                            | Mark a task done                                  | ✓             |
| `daily-log unmark <task-id>`                          | Mark not done                                     | ✓             |
| `daily-log toggle <task-id>`                          | Flip done/not-done                                | ✓             |
| `daily-log add "<text>" [--day Mon] [--type ship]`    | Add a custom task                                 | ✓             |
| `daily-log delete <task-id>`                          | Delete a custom task                              | ✓             |
| `daily-log log [dw_hours] [mood] [bedtime] [protein]` | Daily log (positional args, no flags)             | ✓             |
| `daily-log sync`                                      | Auto-detect week + advance + mark                 | ✓             |
| `daily-log done`                                      | Finish week, advance to next (carries incomplete) | ✓             |
| `daily-log summary [--week W1]`                       | Weekly summary                                    | —             |
| `daily-log set-day <weekday> <type>`                  | Override day-type                                 | ✓             |
| `daily-log set-day --date YYYY-MM-DD <type>`          | Override a specific date                          | ✓             |
| `daily-log set-week Wn`                               | Advance to a week                                 | ✓             |
| `daily-log carryover [from] [to] [--dry-run]`         | Carry incomplete tasks                            | ✓             |
| `daily-log plan show`                                 | Show plan summary                                 | —             |
| `daily-log plan edit`                                 | Open in `$EDITOR`                               | —             |
| `daily-log plan path`                                 | Print file path                                   | —             |
| `daily-log plan reset [--yes]`                        | Reset to empty plan                               | ✓             |
| `daily-log plan export <path>`                        | Export plan to file                               | —             |
| `daily-log plan import <path>`                        | Import a plan from file                           | ✓             |
| `daily-log export <path>`                             | Backup plan file                                  | —             |
| `daily-log import <path>`                             | Restore from backup                               | ✓             |
| `daily-log list-weeks`                                | List all weeks                                    | —             |
| `daily-log list-day-types`                            | List day-types                                    | —             |
| `daily-log show-day <type>`                           | Show a day-type's timetable                       | —             |

## Easy logging (no flags needed)

```bash
daily-log log                    # interactive (press Enter for defaults)
daily-log log 4.2                # just DW hours
daily-log log 4.2 4              # DW + mood
daily-log log 4.2 4 22:30        # DW + mood + bedtime
daily-log log 4.2 4 22:30 y      # DW + mood + bedtime + protein
```

Positional args in order: `dw_hours`, `mood` (1-5), `bedtime` (HH:MM), `protein` (y/n).

## Auto features

1. **Auto-detect week** — detects current week from today's date
2. **Auto-advance** on `today`/`sync` — no manual `set-week` needed
3. **Auto-carryover** — incomplete tasks move to next week (with `carried_over_from` tag)
4. **Auto-festival** — any date listed in your plan's `festival_dates` auto-applies the FEST day-type
5. **Auto-mark** — recording a daily log auto-marks the "Daily log" task done
6. **Auto-schedule switch** — at the week set in `college_start_week`, day-types flip to the second default map (use it for term start, job start, any life change)

All of these read from **your** plan file — nothing about your schedule is
known to the code.

## Bring your own plan

Write one JSON file and point `init --plan` at it. Minimal working example:

```json
{
  "version": "1.0",
  "name": "My 12-Week Plan",
  "total_weeks": 12,
  "start_date": "2026-01-05",
  "current_week": "W1",
  "college_start_week": "W6",
  "day_types": {
    "WORK": {
      "name": "Work day",
      "wake": "08:00",
      "dw_hours": 6.0,
      "exercise": "30-min walk",
      "color": "green",
      "schedule": [["08:00", "Wake"], ["09:00-12:00", "Deep work"]]
    },
    "OFF":  { "name": "Off day", "wake": "09:00", "dw_hours": 0.0, "exercise": "Rest" },
    "FEST": { "name": "Festival day", "wake": "09:00", "dw_hours": 1.0, "exercise": "Family time" },
    "EXAM": { "name": "Exam day", "wake": "06:30", "dw_hours": 2.0, "exercise": "Short walk" }
  },
  "festival_dates": {"2026-02-17": "Some holiday"},
  "default_day_types_w1_w5":   { "monday": "WORK", "saturday": "OFF", "sunday": "OFF" },
  "default_day_types_college": { "monday": "WORK", "saturday": "OFF", "sunday": "OFF" },
  "task_type_meta": {
    "ship":   {"label": "Ship",   "color": "green",   "icon": "◆"},
    "learn":  {"label": "Learn",  "color": "cyan",    "icon": "◇"},
    "anki":   {"label": "Anki",   "color": "magenta", "icon": "▣"},
    "log":    {"label": "Log",    "color": "white",   "icon": "▸"},
    "gate":   {"label": "Gate",   "color": "red",     "icon": "⚑"}
  },
  "weekly_scorecard": [
    {"key": "dw_hours", "label": "DW hours", "target": ">= 12 h"}
  ],
  "daily_log_fields": [
    {"key": "dw_hours", "label": "DW hours", "type": "float"},
    {"key": "mood", "label": "Mood (1-5)", "type": "int"}
  ],
  "date_overrides": {"2026-03-02": "EXAM"},
  "weeks": {
    "W1": {
      "label": "W1 - Foundations",
      "phase": "Stage 1",
      "ship_target": "First artifact shipped",
      "start_date": "2026-01-05",
      "end_date": "2026-01-11",
      "tasks": [
        {"id": "w1-mon-1", "day": "Mon", "date": "2026-01-05",
         "task": "Set up the toolchain", "type": "ship", "done": false},
        {"id": "w1-mon-2", "day": "Mon", "date": "2026-01-05",
         "task": "Anki: 15-minute review", "type": "anki", "done": false},
        {"id": "w1-mon-3", "day": "Mon", "date": "2026-01-05",
         "task": "Daily log", "type": "log", "done": false}
      ],
      "logs": {}
    }
  }
}
```

Rules of thumb: every week key is `W1..Wn`; task ids are `w<week>-<day>-<n>`
(e.g. `w1-mon-2`); `anki`/`log` tasks are never carried over; `life` tasks
are excluded from progress bars. The `plans/example-plan.json` file is a
complete 4-week example you can copy.

## Portability

```bash
# Backup (copies plan.json)
daily-log export backup.json

# Copy to another system (USB, email, cloud)

# Restore on any system
daily-log import backup.json
daily-log today    # → works immediately, all progress preserved
```

## Project structure

```
daily-log-parser/
├── plans/
│   └── example-plan.json       ← generic 4-week demo plan (fake data)
├── src/daily_log_parser/
│   ├── __init__.py             ← version
│   ├── cli.py                  ← CLI (all commands + rich UI)
│   ├── storage.py              ← read/write plan.json (single file)
│   ├── routine.py              ← structural fallbacks only (no plan data)
│   ├── plan.py                 ← plan file helpers
│   └── week_generator.py       ← date math (no plan data)
├── pyproject.toml
└── README.md
```
