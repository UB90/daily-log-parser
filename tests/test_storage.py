from __future__ import annotations

import json
from pathlib import Path
import pytest

from daily_log_parser import storage as S
from daily_log_parser.routine import empty_plan, empty_week
import daily_log_parser.week_generator as wg


def test_plans_dir_and_rejection(tmp_path, monkeypatch):
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    monkeypatch.setenv("DAILY_LOG_DIR", str(plans_dir))

    assert S.plan_dir() == plans_dir
    assert S.is_inside_plans_dir(plans_dir / "my-plan.json")
    assert not S.is_inside_plans_dir(tmp_path / "outside.json")

    with pytest.raises(ValueError, match="Plan file must be in"):
        S.resolve_plan_path(tmp_path / "outside.json")


def test_single_plan_auto_selected(tmp_path, monkeypatch):
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    monkeypatch.setenv("DAILY_LOG_DIR", str(plans_dir))

    plan_file = plans_dir / "my-plan.json"
    plan_data = empty_plan("Test Plan")
    plan_data["weeks"]["W1"] = empty_week(1, "2026-10-12", "2026-10-18")
    with open(plan_file, "w") as f:
        json.dump(plan_data, f)

    assert S.is_initialized()
    assert S.plan_path() == plan_file
    assert S.get_active_plan_name() == "my-plan.json"


def test_direct_modification_in_place(tmp_path, monkeypatch):
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    monkeypatch.setenv("DAILY_LOG_DIR", str(plans_dir))

    plan_file = plans_dir / "my-plan.json"
    plan_data = empty_plan("Test Plan")
    plan_data["weeks"]["W1"] = empty_week(1, "2026-10-12", "2026-10-18")
    plan_data["weeks"]["W1"]["tasks"] = [
        {"id": "t1", "day": "Mon", "task": "Ship code", "type": "ship", "done": False}
    ]
    with open(plan_file, "w") as f:
        json.dump(plan_data, f)

    plan = S.require_plan()
    plan["weeks"]["W1"]["tasks"][0]["done"] = True
    S.save_plan(plan)

    # Verify that the actual file on disk was modified directly
    with open(plan_file, "r") as f:
        reloaded = json.load(f)
    assert reloaded["weeks"]["W1"]["tasks"][0]["done"] is True


def test_multiple_plans_interactive_selection(tmp_path, monkeypatch):
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    monkeypatch.setenv("DAILY_LOG_DIR", str(plans_dir))

    p1 = plans_dir / "plan_a.json"
    p2 = plans_dir / "plan_b.json"
    with open(p1, "w") as f:
        json.dump(empty_plan("Plan A"), f)
    with open(p2, "w") as f:
        json.dump(empty_plan("Plan B"), f)

    # In non-interactive mode without selection, SystemExit should occur
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit):
        S.plan_path()

    # In interactive mode, selecting "2" sets plan_b as active
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    selected = S.plan_path()
    assert selected == p2
    assert S.get_active_plan_name() == "plan_b.json"

    # Switching active plan
    S.set_active_plan("plan_a.json")
    assert S.plan_path() == p1
    assert S.get_active_plan_name() == "plan_a.json"


def test_plans_dir_config_persistence(tmp_path, monkeypatch):
    """Test that once discovered, the Plans directory is remembered when running from an unrelated directory."""
    project_dir = tmp_path / "my_project"
    plans_dir = project_dir / "Plans"
    plans_dir.mkdir(parents=True)
    plan_file = plans_dir / "plan.json"
    plan_file.write_text(json.dumps(empty_plan("Test Plan")), encoding="utf-8")

    # Point config file to a tmp location
    mock_config_file = tmp_path / "config.json"
    monkeypatch.setattr(S, "_CONFIG_FILE", mock_config_file)
    monkeypatch.setattr(S, "_CONFIG_DIR", tmp_path)
    monkeypatch.delenv("DAILY_LOG_DIR", raising=False)

    # 1. Running while cwd is inside the project -> saves to config
    monkeypatch.chdir(project_dir)
    assert S.find_plans_dir() == plans_dir
    assert mock_config_file.is_file()

    # 2. Moving cwd to a completely unrelated folder (like home directory ~ after reboot)
    unrelated_dir = tmp_path / "some_other_folder"
    unrelated_dir.mkdir()
    monkeypatch.chdir(unrelated_dir)

    # Should still resolve to the remembered project Plans folder!
    assert S.find_plans_dir() == plans_dir
    assert S.is_initialized()
    assert S.plan_path() == plan_file
