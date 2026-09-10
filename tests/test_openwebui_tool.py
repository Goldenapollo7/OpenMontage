"""Tests for the Open WebUI integration tool.

The tool is loaded by Open WebUI from a pasted file, so it has to stay a
standalone module: stdlib + pydantic only, no repo imports at module scope.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "integrations" / "open-webui" / "openmontage_tool.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location("openmontage_openwebui_tool", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def tool(tmp_path):
    """A Tools instance pointed at a fake (empty) checkout."""
    module = _load_tool_module()
    instance = module.Tools()
    instance.valves.project_root = str(tmp_path)
    return instance


@pytest.fixture()
def checkout(tmp_path):
    """A Tools instance pointed at a folder that looks like a real clone."""
    (tmp_path / "remotion-composer").mkdir()
    (tmp_path / "remotion-composer" / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pyyaml\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("FAL_KEY=\n", encoding="utf-8")
    module = _load_tool_module()
    instance = module.Tools()
    instance.valves.project_root = str(tmp_path)
    return instance


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------
# Packaging / contract
# ------------------------------------------------------------------

def test_tool_file_is_self_contained():
    """Open WebUI pastes this file into its own environment."""
    source = TOOL_PATH.read_text(encoding="utf-8")
    assert source.startswith('"""')  # Open WebUI parses this frontmatter block
    for field in ("title:", "description:", "version:", "required_open_webui_version:"):
        assert field in source.split('"""')[1], f"frontmatter needs {field}"

    # No repo module may be *imported* at module scope — the only allowed
    # reference is the preflight one-liner string the tool hands to a shell.
    tree = ast.parse(source)
    imported = {
        getattr(node, "module", None) or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported |= {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not {name for name in imported if name.split(".")[0] in {"tools", "lib"}}
    assert "registry.provider_menu_summary()" in source
    assert "registry.import_failures()" in source


def test_valves_expose_project_root_and_safety_switches():
    module = _load_tool_module()
    valves = module.Tools().valves  # defaults, before Open WebUI persists overrides
    assert valves.project_root == ""  # empty until configured
    assert valves.confirm_commands is False
    assert valves.timeout_seconds > 0
    assert valves.max_output_chars >= 500
    assert valves.extra_blocked_patterns == ""


def test_missing_project_root_gives_actionable_error(tmp_path):
    module = _load_tool_module()
    instance = module.Tools()  # project_root left empty
    result = run(instance.om_status())
    assert "project_root" in result
    assert "C:\\OpenMontage" in result


def test_nonexistent_project_root_is_reported(tool, tmp_path):
    tool.valves.project_root = str(tmp_path / "nope")
    assert "does not exist" in run(tool.om_status())


# ------------------------------------------------------------------
# Path safety
# ------------------------------------------------------------------

def test_paths_outside_the_project_are_refused(checkout, tmp_path):
    outside = tmp_path.parent / "secrets.txt"
    result = run(checkout.om_read_file("../secrets.txt"))
    assert "escapes the project folder" in result
    result = run(checkout.om_write_file(str(outside), "nope"))
    assert "escapes the project folder" in result


def test_status_flags_an_incomplete_checkout(tool):
    result = run(tool.om_status())
    assert "Checkout: PROBLEM" in result
    assert "requirements.txt" in result


def test_status_reports_a_complete_checkout(checkout):
    result = run(checkout.om_status())
    assert "Checkout: complete" in result
    assert "Remotion deps: missing" in result  # no node_modules in the fixture


# ------------------------------------------------------------------
# File tools
# ------------------------------------------------------------------

def test_read_write_list_roundtrip(checkout):
    written = run(checkout.om_write_file("projects/demo/brief.md", "# Brief\n"))
    assert "Wrote" in written

    read = run(checkout.om_read_file("projects/demo/brief.md"))
    assert read.strip() == "# Brief"

    listed = run(checkout.om_list_files("projects", "**/*.md"))
    assert "projects/demo/brief.md" in listed


def test_read_file_limits_lines(checkout):
    run(checkout.om_write_file("notes.txt", "one\ntwo\nthree\n"))
    assert run(checkout.om_read_file("notes.txt", max_lines=2)) == "one\ntwo"


def test_read_file_reports_missing_and_directory_cases(checkout):
    assert "no such file" in run(checkout.om_read_file("nope.txt"))
    assert "is a directory" in run(checkout.om_read_file("."))


def test_list_files_reports_no_matches(checkout):
    assert "No matches" in run(checkout.om_list_files(".", "*.mp4"))


# ------------------------------------------------------------------
# Command execution
# ------------------------------------------------------------------

def test_run_command_executes_in_the_project_folder(checkout):
    result = run(
        checkout.om_run_command(
            f'"{sys.executable}" -c "import os; print(os.getcwd())"'
        )
    )
    assert "exit code: 0" in result
    assert str(checkout._root()) in result


def test_run_command_refuses_catastrophic_patterns(checkout):
    for command in ("rm -rf /", "shutdown /s /t 0", "format C:"):
        result = run(checkout.om_run_command(command))
        assert "Refused" in result, command


def test_run_command_honours_extra_blocked_patterns(checkout):
    checkout.valves.extra_blocked_patterns = r"\bdrop\s+table\b"
    assert "Refused" in run(checkout.om_run_command("DROP TABLE users"))
    assert "Refused" not in run(checkout.om_run_command("echo ok"))


def test_run_command_times_out_instead_of_hanging(checkout):
    result = run(
        checkout.om_run_command(
            f'"{sys.executable}" -c "import time; time.sleep(30)"',
            timeout_seconds=2,
        )
    )
    assert "timeout" in result.lower()


def test_trimming_keeps_head_and_tail(checkout):
    checkout.valves.max_output_chars = 500
    text = "A" * 900 + "B" * 900
    trimmed = checkout._trim(text)
    assert "trimmed" in trimmed
    assert len(trimmed) < len(text)
    assert trimmed.startswith("A") and trimmed.endswith("B")


def test_preflight_failure_is_explained_not_raised(tool, monkeypatch):
    """A bare folder has no tools/ package — the model must get a clear message."""
    result = run(tool.om_preflight())
    assert "Preflight failed" in result
    assert "scripts/setup.py" in result
