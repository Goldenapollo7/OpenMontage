"""Discovery must survive a tool module with a missing optional dependency.

Regression: `registry.discover()` walked `tools/` with a bare
`importlib.import_module`, so one module importing numpy (which was missing
from requirements.txt) raised ModuleNotFoundError and killed the entire
preflight. A fresh `pip install -r requirements.txt` was therefore unable to
run the AGENT_GUIDE's mandatory first command.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools.tool_registry import ToolRegistry


@pytest.fixture()
def package_with_broken_module(tmp_path: Path, monkeypatch):
    """A discoverable package containing one importable and one broken tool."""
    package_dir = tmp_path / "demo_pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "good_tool.py").write_text(
        textwrap.dedent(
            """
            from tools.base_tool import BaseTool, ToolResult, ToolTier

            class GoodTool(BaseTool):
                name = "good_tool"
                version = "0.1.0"
                tier = ToolTier.CORE
                capabilities = ["test"]
                dependencies = []

                def execute(self, inputs):
                    return ToolResult(success=True, data={"echo": inputs})
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (package_dir / "broken_tool.py").write_text(
        "import definitely_not_installed_pkg_xyz  # noqa: F401\n"
        "from tools.base_tool import BaseTool\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    return package_dir


def test_discovery_survives_a_missing_optional_dependency(package_with_broken_module):
    registry = ToolRegistry()
    discovered = registry.discover("demo_pkg")

    assert "good_tool" in discovered, "the healthy module must still register"
    failures = registry.import_failures()
    assert any("broken_tool" in name for name in failures)
    assert any(
        "definitely_not_installed_pkg_xyz" in reason for reason in failures.values()
    )


def test_import_failures_are_surfaced_in_preflight_summary(package_with_broken_module):
    """Degraded tools must be visible, not silently absent from the menu."""
    registry = ToolRegistry()
    registry.discover("demo_pkg")
    summary = registry.provider_menu_summary()

    warnings = summary["runtime_warnings"]
    assert any("broken_tool" in warning for warning in warnings), warnings
    assert all(warning.isascii() for warning in warnings), (
        "summary is printed on Windows cp1252 consoles"
    )


def test_clear_resets_import_failures(package_with_broken_module):
    registry = ToolRegistry()
    registry.discover("demo_pkg")
    assert registry.import_failures()
    registry.clear()
    assert registry.import_failures() == {}


def test_real_repo_discovers_in_this_environment():
    """Whatever is installed here, discovery must not raise."""
    registry = ToolRegistry()
    registry.discover()
    assert registry.list_all(), "at least some tools should always register"
    summary = registry.provider_menu_summary()
    assert set(summary) >= {"composition_runtimes", "capabilities", "runtime_warnings"}
