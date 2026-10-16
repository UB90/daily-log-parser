from __future__ import annotations

import json
from pathlib import Path
import pytest

from daily_log_parser.cli import main
from daily_log_parser.routine import empty_plan, empty_week
import daily_log_parser.storage as S


def test_cli_mark_directly_modifies_plan_file(tmp_path, monkeypatch):
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    monkeypatch.setenv("DAILY_LOG_DIR", str(plans_dir))

    plan_file = plans_dir / "my-plan.json"
    plan_data = empty_plan("Test Plan")
    plan_data["current_week"] = "W1"
    plan_data["weeks"]["W1"] = empty_week(1, "2026-10-12", "2026-10-18")
    plan_data["weeks"]["W1"]["tasks"] = [
        {"id": "w1-mon-1", "day": "Mon", "task": "Ship portfolio", "type": "ship", "done": False}
    ]
    with open(plan_file, "w") as f:
        json.dump(plan_data, f)

    # Run daily-log mark w1-mon-1
    rc = main(["mark", "w1-mon-1"])
    assert rc == 0

    # Verify that plan_file was directly modified on disk!
    with open(plan_file, "r") as f:
        saved = json.load(f)
    task = saved["weeks"]["W1"]["tasks"][0]
    assert task["done"] is True
    assert "completed_on" in task

    # Run daily-log unmark w1-mon-1
    rc = main(["unmark", "w1-mon-1"])
    assert rc == 0

    with open(plan_file, "r") as f:
        saved = json.load(f)
    task = saved["weeks"]["W1"]["tasks"][0]
    assert task["done"] is False
    assert "completed_on" not in task


def test_cli_rejects_plan_outside_plans_folder(tmp_path, monkeypatch):
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    monkeypatch.setenv("DAILY_LOG_DIR", str(plans_dir))

    outside = tmp_path / "outside.json"
    outside.write_text("{}")

    rc = main(["init", "--plan", str(outside)])
    assert rc == 1


def test_cli_plan_list_and_select(tmp_path, monkeypatch, capsys):
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    monkeypatch.setenv("DAILY_LOG_DIR", str(plans_dir))

    p1 = plans_dir / "alpha.json"
    p2 = plans_dir / "beta.json"
    with open(p1, "w") as f:
        json.dump(empty_plan("Alpha"), f)
    with open(p2, "w") as f:
        json.dump(empty_plan("Beta"), f)

    # Select beta
    rc = main(["plan", "select", "beta.json"])
    assert rc == 0
    assert S.get_active_plan_name() == "beta.json"

    # List
    rc = main(["plan", "list"])
    assert rc == 0


def test_cli_full_workflow(tmp_path, monkeypatch):
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    monkeypatch.setenv("DAILY_LOG_DIR", str(plans_dir))

    # Initialize empty plan
    rc = main(["init", "--force"])
    assert rc == 0
    active = S.plan_path()
    assert active.exists()

    # Add a task
    rc = main(["add", "Write docs", "--day", "Mon", "--type", "ship"])
    assert rc == 0

    # Toggle task
    with open(active) as f:
        data = json.load(f)
    t = data["weeks"]["W1"]["tasks"][0]
    tid = t["id"]

    rc = main(["toggle", tid])
    assert rc == 0

    with open(active) as f:
        data = json.load(f)
    assert data["weeks"]["W1"]["tasks"][0]["done"] is True

    # Check today and week views
    assert main(["today"]) == 0
    assert main(["week"]) == 0
    assert main(["summary"]) == 0
    assert main(["list-weeks"]) == 0
    assert main(["list-day-types"]) == 0
    assert main(["plan", "show"]) == 0
    assert main(["plan", "path"]) == 0

    # Log metrics
    assert main(["log", "4.0", "5", "23:00", "y"]) == 0

    # Export plan with half-completed progress
    backup_file = tmp_path / "backup.json"
    assert main(["export", str(backup_file)]) == 0
    assert backup_file.exists()
    with open(backup_file) as f:
        exported_data = json.load(f)
    # Verify half-completed progress is preserved
    assert exported_data["weeks"]["W1"]["tasks"][0]["done"] is True

    # Import plan back into Plans with same name should require --force
    assert main(["import", str(backup_file)]) == 0  # first time creates backup.json in Plans/
    assert (plans_dir / "backup.json").exists()

    # Second import without --force fails because it already exists
    assert main(["import", str(backup_file)]) == 1

    # Second import with --force succeeds
    assert main(["import", "--force", str(backup_file)]) == 0
    assert S.get_active_plan_name() == "backup.json"
