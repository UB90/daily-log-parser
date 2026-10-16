"""Storage: read/write the single plan.json file.

Location rules (no personal data here, just paths):
- default: ~/.daily-log/plan.json
- override: set env var DAILY_LOG_DIR to any directory

Every command that changes state saves immediately (atomic write).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

PLAN_FILENAME = "plan.json"

ENV_DIR = "DAILY_LOG_DIR"


def plan_dir() -> Path:
    """Directory that holds plan.json."""
    custom = os.environ.get(ENV_DIR)
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".daily-log"


def plan_path() -> Path:
    """Full path of the single plan file."""
    return plan_dir() / PLAN_FILENAME


def is_initialized() -> bool:
    return plan_path().is_file()


def require_plan() -> dict:
    """Load plan.json or die with a friendly message."""
    if not is_initialized():
        raise SystemExit(
            "No plan found at " + str(plan_path()) + "\n"
            "Get started:   daily-log init                      (empty starter plan)\n"
            "            or daily-log init --plan <your-plan.json>\n"
            "       example: daily-log init --plan plans/example-plan.json"
        )
    return load_plan()


def load_plan() -> dict:
    """Load and lightly validate the plan file."""
    try:
        with open(plan_path(), "r", encoding="utf-8") as fh:
            plan = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            "plan.json is not valid JSON (" + str(exc) + ").\n"
            "Fix it with:  daily-log plan edit\n"
            "Or restore:   daily-log import <backup.json>"
        ) from exc
    if not isinstance(plan, dict) or "weeks" not in plan:
        raise SystemExit(
            "plan.json does not look like a plan (missing 'weeks').\n"
            "Re-initialize:  daily-log init --force --plan <your-plan.json>"
        )
    return plan


def save_plan(plan: dict) -> None:
    """Atomically save the plan file (tmp file + rename, same directory)."""
    path = plan_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".plan-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def copy_plan_file(src: str | Path, dest: str | Path) -> None:
    """Copy a plan file (used by init / export / import).

    If *dest* is an existing directory, the file is placed inside it
    with the same name as the source file.
    """
    src = Path(src)
    if not src.is_file():
        raise SystemExit("File not found: " + str(src))
    dest = Path(dest)
    if dest.is_dir():
        dest = dest / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())
