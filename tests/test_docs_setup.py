"""Guardrails for the install instructions.

Regression test for a real Windows bug report: the README's install recipe was
a single ``&&`` chain::

    pip install -r requirements.txt && cd remotion-composer && npm install && ...

That is valid bash but a hard parser error in PowerShell 5.1, which is what
ships with Windows 10/11::

    The token '&&' is not a valid statement separator in this version.

The docs are copy-pasteable, so these tests check that the setup path stays
shell-agnostic:

* Windows-labelled code blocks parse on PowerShell 5.1 (no ``&&`` / ``||``)
* the README install section contains no shell chaining at all
* ``scripts/setup.py`` exists, runs standalone, and installs everything
* every ``make <target>`` named in the docs actually exists in the Makefile
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = REPO_ROOT / "scripts" / "setup.py"
MAKEFILE = REPO_ROOT / "Makefile"

# Fence languages whose content a Windows user is expected to paste into
# PowerShell 5.1 or CMD.
WINDOWS_FENCE_LANGS = {"powershell", "pwsh", "ps1", "cmd", "bat", "dosbatch"}

# Escape hatch for the rare block that genuinely needs PowerShell 7+.
PWSH7_MARKERS = ("# requires powershell 7", "#requires powershell 7", "# pwsh7")

_FENCE_RE = re.compile(r"^\s*```(\S*)\s*$")
_MAKE_INLINE_RE = re.compile(r"`make\s+([a-z][a-z0-9-]*)`")
_MAKE_LINE_RE = re.compile(r"^\s*\$?\s*make\s+([a-z][a-z0-9-]*)\s*$")


@dataclass
class CodeBlock:
    path: Path
    lang: str
    start_line: int
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def where(self) -> str:
        return f"{self.path.relative_to(REPO_ROOT)}:{self.start_line}"


def _doc_paths() -> list[Path]:
    paths = [REPO_ROOT / "README.md", REPO_ROOT / "AGENT_GUIDE.md"]
    docs = REPO_ROOT / "docs"
    if docs.is_dir():
        paths.extend(sorted(docs.rglob("*.md")))
    return [p for p in paths if p.exists()]


def _code_blocks(path: Path) -> list[CodeBlock]:
    return _code_blocks_in(path, path.read_text(encoding="utf-8").splitlines())


def _code_blocks_in(path: Path, lines: list[str], *, offset: int = 0) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []
    lang: str | None = None
    start = 0
    current: list[str] = []
    for number, line in enumerate(lines, start=1):
        fence = _FENCE_RE.match(line)
        if fence:
            if lang is None:
                lang = fence.group(1).lower()
                start = number + offset
                current = []
            else:
                blocks.append(CodeBlock(path, lang, start, current))
                lang = None
            continue
        if lang is not None:
            current.append(line)
    return blocks


def _has_shell_chaining(line: str) -> bool:
    """True when a line chains commands with ``&&`` or ``||``.

    Those operators are PowerShell 7 additions; PowerShell 5.1 rejects them at
    parse time, which is exactly the failure this file guards against.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    return "&&" in stripped or "||" in stripped


# ------------------------------------------------------------------
# Docs parse on the shells the docs claim to support
# ------------------------------------------------------------------


@pytest.mark.parametrize("path", _doc_paths(), ids=lambda p: p.name)
def test_windows_blocks_parse_on_powershell_51(path: Path):
    offenders = []
    for block in _code_blocks(path):
        if block.lang not in WINDOWS_FENCE_LANGS:
            continue
        if any(marker in block.text.lower() for marker in PWSH7_MARKERS):
            continue
        for line in block.lines:
            if _has_shell_chaining(line):
                offenders.append(f"{block.where()} -> {line.strip()}")
    assert not offenders, (
        "Windows code blocks must not chain commands with && or || "
        "(parser error on PowerShell 5.1):\n" + "\n".join(offenders)
    )


def test_readme_install_section_is_shell_agnostic():
    """The exact reported bug: an && chain in the install recipe.

    Prose may *explain* that ``&&`` is broken on PowerShell 5.1 — what matters
    is that no runnable code block in the section chains commands.
    """
    readme_path = REPO_ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    marker = "### Install & Run"
    start = readme.index(marker)
    offset = readme[:start].count("\n") + 1
    rest = readme[start + len(marker):]
    nxt = rest.find("\n### ")
    section_lines = (rest if nxt == -1 else rest[:nxt]).splitlines()

    offenders = []
    for block in _code_blocks_in(readme_path, section_lines, offset=offset):
        for line in block.lines:
            if _has_shell_chaining(line):
                offenders.append(f"{block.where()} -> {line.strip()}")

    assert not offenders, (
        "The README install section is pasted into PowerShell on Windows; use "
        "one command per line instead of `a && b`:\n" + "\n".join(offenders)
    )


def test_readme_points_windows_users_at_the_cross_platform_script():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "python scripts\\setup.py" in readme
    assert "PowerShell 5.1" in readme  # explains why && is not used


# ------------------------------------------------------------------
# The setup script itself
# ------------------------------------------------------------------


def test_setup_script_exists_and_is_standalone():
    assert SETUP_SCRIPT.is_file(), "scripts/setup.py is the one-command setup path"
    tree = ast.parse(SETUP_SCRIPT.read_text(encoding="utf-8"))

    # Repo code may only be imported in a guarded probe — setup has to run on a
    # bare Python before requirements.txt is installed.
    repo_imports = {
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and (getattr(node, "module", "") or "").startswith("tools")
    }
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            guarded.update(
                child.lineno
                for child in ast.walk(node)
                if isinstance(child, (ast.Import, ast.ImportFrom))
            )
    assert repo_imports <= guarded, (
        "only the optional HyperFrames probe may import repo code, and it must "
        "be wrapped in try/except"
    )

    # Everything is spawned as an argument list, never through a shell — that is
    # what makes the script shell-agnostic on Windows.
    shell_calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", None) in
        {"Popen", "run", "call", "check_call", "check_output"}
        and any(
            kw.arg == "shell" and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        )
    ]
    assert not shell_calls, f"subprocess calls using shell=True: {shell_calls}"


def test_setup_script_messages_never_hand_out_and_and_chains():
    """The script's own advice must follow the rule it enforces."""
    tree = ast.parse(SETUP_SCRIPT.read_text(encoding="utf-8"))
    printers = {"_emit", "_note", "_line", "_header"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in printers:
            for text in (
                child.value
                for child in ast.walk(node)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            ):
                if "&&" in text:
                    offenders.append(f"scripts/setup.py:{node.lineno} -> {text}")
    assert not offenders, (
        "setup output is pasted by Windows users too; use one command per line:\n"
        + "\n".join(offenders)
    )


def test_setup_script_help_works():
    proc = subprocess.run(
        [sys.executable, str(SETUP_SCRIPT), "--help"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--check-only" in proc.stdout
    assert "--dry-run" in proc.stdout


def test_setup_script_dry_run_lists_every_step_without_chaining():
    proc = subprocess.run(
        [sys.executable, str(SETUP_SCRIPT), "--dry-run"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    assert "pip install -r requirements.txt" in out
    assert "npm install" in out
    assert "piper-tts" in out
    assert "&&" not in out
    assert "would copy" in out or ".env already exists" in out


def test_check_only_reports_toolchain():
    proc = subprocess.run(
        [sys.executable, str(SETUP_SCRIPT), "--check-only"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180,
    )
    # Exit code depends on the machine (Node/FFmpeg may be missing) — either
    # way the report must name the checked tools.
    assert "Python" in proc.stdout
    assert "Node.js" in proc.stdout or "Node.js not found" in proc.stdout


# ------------------------------------------------------------------
# Windows entry points and Makefile wiring
# ------------------------------------------------------------------


def test_windows_wrappers_delegate_to_the_script():
    for name, needle in (("setup.ps1", "scripts\\setup.py"),
                         ("setup.cmd", "scripts\\setup.py")):
        wrapper = REPO_ROOT / name
        assert wrapper.is_file(), f"{name} is the Windows entry point"
        assert needle in wrapper.read_text(encoding="utf-8")


def test_powershell_wrapper_has_no_powershell7_only_syntax():
    text = (REPO_ROOT / "setup.ps1").read_text(encoding="utf-8")

    # Comments (line and block) are allowed to talk about &&; code is not.
    code_lines: list[str] = []
    in_block_comment = False
    for line in text.splitlines():
        if in_block_comment:
            in_block_comment = "#>" not in line
            continue
        if line.lstrip().startswith("<#"):
            in_block_comment = "#>" not in line.split("<#", 1)[1]
            continue
        code_lines.append(line)

    offenders = [line.strip() for line in code_lines if _has_shell_chaining(line)]
    assert not offenders, (
        "setup.ps1 must run on PowerShell 5.1 (no && / || chaining): "
        + "; ".join(offenders)
    )


def test_makefile_setup_delegates_to_the_script():
    makefile = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^setup:\n((?:\t.*\n)+)", makefile, re.MULTILINE)
    assert match, "Makefile has a `setup` target"
    assert "scripts/setup.py" in match.group(1), (
        "`make setup` must call scripts/setup.py so Windows and POSIX paths "
        "cannot drift apart"
    )
    assert "setup-check" in makefile


def test_documented_make_targets_exist():
    makefile = MAKEFILE.read_text(encoding="utf-8")
    targets = set(re.findall(r"^([a-zA-Z0-9_-]+):", makefile, re.MULTILINE))

    referenced: dict[str, str] = {}
    for path in _doc_paths():
        text = path.read_text(encoding="utf-8")
        for target in _MAKE_INLINE_RE.findall(text):
            referenced.setdefault(target, str(path.relative_to(REPO_ROOT)))
        for block in _code_blocks(path):
            for line in block.lines:
                for target in _MAKE_LINE_RE.findall(line):
                    referenced.setdefault(target, str(path.relative_to(REPO_ROOT)))

    missing = {t: src for t, src in referenced.items() if t not in targets}
    assert not missing, f"docs reference make targets that do not exist: {missing}"
