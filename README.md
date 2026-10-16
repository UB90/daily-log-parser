# daily-log-parser

A fast, privacy-first CLI plan tracker. **One file. File-driven. Offline.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-1.0.1-green.svg)](pyproject.toml)

All plan data (tasks, day-types, festivals, timetables, and daily logs) lives in a single JSON file of **yours**. The application is a pure handler: it reads your file, modifies it with atomic writes, and displays clean terminal UI via Rich. No external databases, no telemetry, no cloud lock-in.

```
~/.daily-log/
└── plan.json    ← EVERYTHING: tasks + completion state + daily logs + overrides
```

---

## Installation

Requires **Python 3.10+**.

### From GitHub (recommended)
```bash
# Using uv (fastest)
uv tool install git+https://github.com/UB90/daily-log-parser.git

# Using pip
pip install git+https://github.com/UB90/daily-log-parser.git
```

### From Local Source
```bash
git clone https://github.com/UB90/daily-log-parser.git
cd daily-log-parser

# Install globally via uv tool
uv tool install .

# Or editable install for development
pip install -e ".[dev]"
```

> **Tip:** Set the `DAILY_LOG_DIR` environment variable to store `plan.json` in a custom location instead of `~/.daily-log`.

---

## Quick Start

### 1. Initialize your plan

```bash
# Option A: Start from a clean starter plan template
daily-log init

# Option B: Load your existing plan JSON file
daily-log init --plan /path/to/your-plan.json
```

### 2. Daily Workflow

```bash
# Morning: check today's tasks and routine timetable
daily-log today

# Mark a task complete (instantly saved to plan.json)
daily-log mark w1-mon-1

# Flip between done / not-done
daily-log toggle w1-mon-1

# Sync: auto-detect week and carry over unfinished tasks from earlier days to today
daily-log sync

# End of day: log metrics in seconds (deep work hours, mood, bedtime, protein)
daily-log log 4.5 4 22:30 y

# View full week overview
daily-log week

# Weekly review & advance to next week (carries incomplete tasks forward)
daily-log summary
daily-log done
```

---

## All Commands

| Command | Action | Saves File |
| :--- | :--- | :---: |
| `daily-log init [--plan <path>] [--force]` | Initialize new plan or load from file | ✓ |
| `daily-log today` | Show today's tasks, schedule timetable & day-type | — |
| `daily-log week [--week W1]` | Show full week view broken down by day | — |
| `daily-log mark <task-id>` | Mark task as completed | ✓ |
| `daily-log unmark <task-id>` | Mark task as incomplete | ✓ |
| `daily-log toggle <task-id>` | Toggle task done/undone | ✓ |
| `daily-log add "<text>" [--day Mon] [--type ship]` | Add a new task to current week | ✓ |
| `daily-log delete <task-id>` | Delete a custom task | ✓ |
| `daily-log log [dw] [mood] [bedtime] [protein]` | Record daily metric log (supports interactive mode) | ✓ |
| `daily-log sync` | Auto-detect date/week + carry over tasks from earlier days | ✓ |
| `daily-log done` | Close week and advance to next (carries over undone tasks) | ✓ |
| `daily-log summary [--week W1]` | Show weekly progress statistics, gates, and metrics | — |
| `daily-log set-day <weekday> <type>` | Override default day-type for a weekday | ✓ |
| `daily-log set-day --date YYYY-MM-DD <type>` | Override day-type for a specific date | ✓ |
| `daily-log set-week Wn` | Jump directly to a specific week | ✓ |
| `daily-log carryover [from] [to] [--dry-run]` | Carry incomplete tasks forward manually | ✓ |
| `daily-log plan show` | Display plan metadata, version, and totals | — |
| `daily-log plan edit` | Open `plan.json` directly in your `$EDITOR` | — |
| `daily-log plan path` | Print filesystem path to active `plan.json` | — |
| `daily-log plan reset [--yes]` | Reset plan to an empty starter skeleton | ✓ |
| `daily-log export <path>` | Backup plan file or write into a target directory | — |
| `daily-log import <path>` | Restore plan from backup file | ✓ |
| `daily-log list-weeks` | List all weeks with start and end dates | — |
| `daily-log list-day-types` | List all registered day types and routines | — |
| `daily-log show-day <type>` | View detailed daily schedule for a day type | — |

---

## Features

### Intuitive Daily Logging
Log your key daily metrics without complex flags:
```bash
daily-log log                    # Interactive prompts with smart defaults
daily-log log 4.2                # Deep work hours only
daily-log log 4.2 4              # Deep work + mood (1-5)
daily-log log 4.2 4 22:30        # Deep work + mood + bedtime
daily-log log 4.2 4 22:30 y      # Deep work + mood + bedtime + hit protein target
```

### Automated Flow
1. **Intra-Week Task Rollover (`sync`)** — Incomplete non-habit tasks from earlier days automatically roll over to today and display a helpful `(moved from <Day>)` indicator.
2. **Auto-Detect Week** — Detects current week from system date so you never need to manually switch weeks.
3. **Cross-Week Carryover (`done`)** — Unfinished weekly tasks advance to the next week tagged with `(carried from W<n>)`.
4. **Auto-Festivals & Overrides** — Dates declared in `festival_dates` automatically trigger holiday timetables and day types.
5. **Auto-Mark on Log** — Saving your end-of-day log automatically checks off the daily "Daily log" task.
6. **Habit Protection** — Habit tasks (`anki`, `log`) stay anchored to their day and are never rolled over.

---

## Bring Your Own Plan

Your plan is simply a JSON file. Minimal valid example:

```json
{
  "version": "1.0",
  "name": "My Learning Plan",
  "total_weeks": 12,
  "start_date": "2026-01-05",
  "current_week": "W1",
  "college_start_week": "W6",
  "day_types": {
    "WORK": {
      "name": "Work Day",
      "wake": "08:00",
      "dw_hours": 6.0,
      "exercise": "30-min walk",
      "color": "green",
      "schedule": [["08:00", "Wake"], ["09:00-12:00", "Deep work"]]
    },
    "OFF": {
      "name": "Rest Day",
      "wake": "09:00",
      "dw_hours": 0.0,
      "exercise": "Rest"
    }
  },
  "festival_dates": {},
  "default_day_types_w1_w5": { "monday": "WORK", "saturday": "OFF", "sunday": "OFF" },
  "default_day_types_college": { "monday": "WORK", "saturday": "OFF", "sunday": "OFF" },
  "task_type_meta": {
    "ship":  {"label": "Ship",  "color": "green",   "icon": "◆"},
    "learn": {"label": "Learn", "color": "cyan",    "icon": "◇"},
    "anki":  {"label": "Anki",  "color": "magenta", "icon": "▣"},
    "log":   {"label": "Log",   "color": "white",   "icon": "▸"},
    "gate":  {"label": "Gate",  "color": "red",     "icon": "⚑"}
  },
  "weekly_scorecard": [
    {"key": "dw_hours", "label": "DW hours", "target": ">= 12 h"}
  ],
  "daily_log_fields": [
    {"key": "dw_hours", "label": "DW hours", "type": "float"},
    {"key": "mood", "label": "Mood (1-5)", "type": "int"}
  ],
  "date_overrides": {},
  "weeks": {
    "W1": {
      "label": "W1 - Kickoff",
      "phase": "Stage 1",
      "ship_target": "Initial deliverable",
      "start_date": "2026-01-05",
      "end_date": "2026-01-11",
      "tasks": [
        {"id": "w1-mon-1", "day": "Mon", "date": "2026-01-05", "task": "Configure project", "type": "ship", "done": false},
        {"id": "w1-mon-2", "day": "Mon", "date": "2026-01-05", "task": "Daily log", "type": "log", "done": false}
      ],
      "logs": {}
    }
  }
}
```

---

## Portability & Backups

Your data is 100% portable:
```bash
# Backup to a file or directory
daily-log export ~/backups/
daily-log export ~/backups/plan-backup.json

# Restore on any computer
daily-log import ~/backups/plan-backup.json

# Verify state
daily-log today
```

---

## Version History

### v1.0.1
- **Directory Export Fix:** `daily-log export` and `daily-log plan export` automatically append `plan.json` when targeting a directory, preventing `IsADirectoryError`.
- **Intra-Week Task Rollover:** `daily-log sync` carries forward uncompleted non-habit tasks from earlier days of the week to today.
- **Visual Moved Indicators:** Tasks shifted across days or weeks clearly display origin badges like `(moved from Mon)` and `(carried from W1)` in `today` and `week` views.


### v1.0.0
- Initial featuring atomic JSON storage, custom routine day-types, interactive daily metric logging, and weekly scorecard tracking.

---

## Project Structure

```
daily-log-parser/
├── src/daily_log_parser/
│   ├── __init__.py             ← version & package metadata
│   ├── cli.py                  ← CLI commands and Rich terminal presentation
│   ├── storage.py              ← atomic read/write for plan.json
│   ├── routine.py              ← fallback structures & timetable rendering
│   ├── plan.py                 ← plan inspection, carryovers & task manipulation
│   └── week_generator.py       ← calendar date math
├── pyproject.toml              ← package configuration & dependencies
└── README.md
```
