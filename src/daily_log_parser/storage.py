"""Storage: read/write plan files directly in the Plans folder.

Location resolution (in order):
1. DAILY_LOG_DIR environment variable (points to or contains a Plans/ folder).
2. Saved path in ~/.config/daily-log/config.json (persisted on first use).
3. Walk upward from cwd looking for a Plans/ or plans/ directory.

Once found, the Plans directory is saved to config so future invocations
from any working directory (including after a reboot) keep working.

Commands directly modify the active plan file in-place with atomic writes.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

PLAN_FILENAME = "plan.json"
ACTIVE_FILE_TRACKER = ".active_plan"
ENV_DIR = "DAILY_LOG_DIR"

_CONFIG_DIR = Path.home() / ".config" / "daily-log"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


# --------------------------------------------------------- config helpers

def _load_config() -> dict:
    """Load the tiny config file, or return empty dict."""
    if _CONFIG_FILE.is_file():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(cfg: dict) -> None:
    """Persist config to ~/.config/daily-log/config.json."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _save_plans_dir(d: Path) -> None:
    """Remember the resolved Plans directory for future sessions."""
    if os.environ.get(ENV_DIR):
        return  # Do not pollute user config during tests or explicit env overrides
    cfg = _load_config()
    cfg["plans_dir"] = str(d.resolve())
    _save_config(cfg)


# ------------------------------------------------------- Plans dir lookup

def find_plans_dir() -> Path:
    """Find the Plans directory.

    Order of resolution:
    1. DAILY_LOG_DIR environment variable (used for testing or explicit overrides).
    2. Walk upwards from current working directory for a Plans/ or plans/ directory.
       If found, it is saved to ~/.config/daily-log/config.json.
    3. Saved path from ~/.config/daily-log/config.json (allows running from anywhere post-reboot).
    4. Fallback: cwd / 'Plans'.
    """
    # 1. Environment variable override
    custom = os.environ.get(ENV_DIR)
    if custom:
        p = Path(custom).expanduser().resolve()
        for name in ("Plans", "plans"):
            if (p / name).is_dir():
                return p / name
        return p

    # 2. Walk upward from cwd
    cwd = Path.cwd().resolve()
    for base in [cwd] + list(cwd.parents):
        for name in ("Plans", "plans"):
            cand = base / name
            if cand.is_dir():
                try:
                    _save_plans_dir(cand)
                except Exception:
                    pass
                return cand

    # 3. Previously saved path in config
    cfg = _load_config()
    saved = cfg.get("plans_dir")
    if saved:
        sp = Path(saved).resolve()
        if sp.is_dir():
            return sp

    # 4. Fallback: ./Plans (will be created on init)
    return cwd / "Plans"


def plan_dir() -> Path:
    """Directory that holds plan files (must be Plans/)."""
    return find_plans_dir()


# --------------------------------------------------------- path helpers

def is_inside_plans_dir(path: Path | str) -> bool:
    """Return True if path is inside plan_dir()."""
    try:
        p = Path(path).expanduser().resolve()
        p_dir = plan_dir().resolve()
        p.relative_to(p_dir)
        return True
    except (ValueError, RuntimeError):
        return False


def resolve_plan_path(path_or_name: str | Path) -> Path:
    """Resolve a user-provided plan path or filename, ensuring it is in Plans/."""
    p = Path(path_or_name).expanduser()
    if not p.is_absolute():
        if p.exists():
            p = p.resolve()
        elif (plan_dir() / p).exists():
            p = (plan_dir() / p).resolve()
        else:
            p = (plan_dir() / p).resolve()
    else:
        p = p.resolve()

    if not is_inside_plans_dir(p):
        raise ValueError(
            f"Plan file must be in the '{plan_dir().name}' folder ({plan_dir()}). "
            f"'{path_or_name}' is outside of it."
        )
    return p


# -------------------------------------------------- plan file discovery

def list_plan_files() -> List[Path]:
    """Return all .json plan files located directly in plan_dir()."""
    d = plan_dir()
    if not d.is_dir():
        return []
    return sorted(
        [
            f for f in d.glob("*.json")
            if not f.name.startswith(".") and not f.name.endswith(".tmp") and f.is_file()
        ],
        key=lambda p: p.name.lower(),
    )


def get_active_plan_name() -> Optional[str]:
    """Get the filename of the active plan from .active_plan, if valid."""
    d = plan_dir()
    tracker = d / ACTIVE_FILE_TRACKER
    if tracker.is_file():
        try:
            name = tracker.read_text(encoding="utf-8").strip()
            if name and (d / name).is_file():
                return name
        except Exception:
            pass
    return None


def set_active_plan(plan_file: Path | str) -> Path:
    """Set the active plan file (must be inside Plans/)."""
    path = resolve_plan_path(plan_file)
    if not path.is_file():
        raise FileNotFoundError(f"Plan file not found: {path}")
    d = plan_dir()
    d.mkdir(parents=True, exist_ok=True)
    tracker = d / ACTIVE_FILE_TRACKER
    tracker.write_text(path.name, encoding="utf-8")
    return path


def select_plan_interactively(json_files: List[Path]) -> Path:
    """Prompt the user in terminal to choose from multiple plan files."""
    if not sys.stdin.isatty():
        file_list = ", ".join(f.name for f in json_files)
        raise SystemExit(
            f"Multiple plan files found in {plan_dir().name}/: {file_list}\n"
            f"Please specify which plan to use: daily-log plan select <filename>"
        )

    print(f"\nMultiple plan files found in '{plan_dir()}':")
    for i, f in enumerate(json_files, 1):
        extra = ""
        try:
            with open(f, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
                name = meta.get("name")
                weeks = len(meta.get("weeks", {}))
                extra = f" ({name}, {weeks} weeks)" if name else f" ({weeks} weeks)"
        except Exception:
            pass
        print(f"  {i}) {f.name}{extra}")

    while True:
        try:
            choice = input(f"\nSelect a plan to use [1-{len(json_files)}]: ").strip()
            if not choice:
                continue
            idx = int(choice)
            if 1 <= idx <= len(json_files):
                selected = json_files[idx - 1]
                set_active_plan(selected)
                print(f"Active plan set to: {selected.name}\n")
                return selected
        except (ValueError, EOFError):
            pass
        print(f"Please enter a number between 1 and {len(json_files)}.")


def plan_path() -> Path:
    """Full path of the active plan file inside Plans/."""
    d = plan_dir()
    active_name = get_active_plan_name()
    if active_name:
        return d / active_name

    if d.is_dir():
        files = list_plan_files()
        if len(files) == 1:
            set_active_plan(files[0])
            return files[0]
        elif len(files) > 1:
            return select_plan_interactively(files)

    return d / PLAN_FILENAME


# ------------------------------------------------- load / save / init

def is_initialized() -> bool:
    """Check if a plan file exists and is available in Plans/."""
    d = plan_dir()
    if not d.is_dir():
        return False
    active = get_active_plan_name()
    if active and (d / active).is_file():
        return True
    return len(list_plan_files()) > 0


def require_plan() -> dict:
    """Load plan or die with a friendly message."""
    if not is_initialized():
        d = plan_dir()
        raise SystemExit(
            f"No plan found in {d}\n"
            f"Get started:   daily-log init                      (empty starter plan in {d.name}/)\n"
            f"            or daily-log import <your-plan.json>    (import from anywhere)"
        )
    return load_plan()


def load_plan(path: Optional[Path] = None) -> dict:
    """Load and lightly validate the plan file."""
    p = path or plan_path()
    try:
        with open(p, "r", encoding="utf-8") as fh:
            plan = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{p.name} is not valid JSON ({exc}).\n"
            "Fix it with:  daily-log plan edit\n"
            "Or restore:   daily-log import <backup.json>"
        ) from exc
    except FileNotFoundError:
        raise SystemExit(f"Plan file not found: {p}")
    if not isinstance(plan, dict) or "weeks" not in plan:
        raise SystemExit(
            f"{p.name} does not look like a plan (missing 'weeks').\n"
            f"Re-initialize:  daily-log init --force --plan {p.name}"
        )
    return plan


def save_plan(plan: dict, target_path: Optional[Path] = None) -> None:
    """Atomically save the plan file directly in Plans/."""
    path = target_path or plan_path()
    if not is_inside_plans_dir(path):
        raise ValueError(
            f"Cannot save plan outside Plans directory ({plan_dir()}): {path}"
        )
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
    # Persist the Plans dir path so future sessions from any cwd work.
    _save_plans_dir(path.parent)
    set_active_plan(path)


