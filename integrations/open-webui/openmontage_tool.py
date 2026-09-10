"""
title: OpenMontage
author: OpenMontage
author_url: https://github.com/calesthio/OpenMontage
description: Drive the OpenMontage video production system from Open WebUI — run pipeline commands, read and write project files, and run preflight discovery. Runs on the machine hosting your Open WebUI backend, inside your OpenMontage clone.
required_open_webui_version: 0.6.31
version: 0.1.0
license: AGPL-3.0
"""

# ---------------------------------------------------------------------------
# What this is
# ---------------------------------------------------------------------------
# Open WebUI's default code execution (Pyodide) runs in your browser and cannot
# touch your OpenMontage clone. This Workspace Tool runs *in the Open WebUI
# backend process*, so the model gets:
#
#   * a real shell in your project folder (Python, npm/npx, ffmpeg, git)
#   * file reads/writes scoped to the project folder
#   * the repo's own preflight command, so the model can show the provider menu
#
# Pair it with a system prompt that points the model at AGENT_GUIDE.md — see
# integrations/open-webui/README.md for the paste-ready prompt and setup steps.
#
# Security: this executes commands with the privileges of the user running the
# Open WebUI backend. Keep the instance local, don't hand Workspace access to
# untrusted users, and consider setting confirm_commands = true.
# ---------------------------------------------------------------------------

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

# Files that only exist in a real OpenMontage clone.
CHECKOUT_FILES = ("requirements.txt", "remotion-composer/package.json", ".env.example")

# The documented preflight from AGENT_GUIDE.md — the model should run this
# before proposing a plan so the user sees what is actually available. It is
# executed with the repo on sys.path, as a `python -c` one-liner.
PREFLIGHT_CODE = (
    "from tools.tool_registry import registry; import json; registry.discover(); "
    "print(json.dumps({'menu': registry.provider_menu_summary(), "
    "'import_failures': registry.import_failures()}))"
)


def _interpreter_candidates() -> list[str]:
    """Interpreters to try for OpenMontage scripts, most specific first.

    The Open WebUI backend Python may be the one holding the repo's
    dependencies (pip install -r requirements.txt), or the repo may be on a
    separate system Python while Open WebUI runs in a venv. Try both.
    """
    seen: list[str] = []
    for candidate in (sys.executable, "python", "python3"):
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen

# Refused outright — these are never part of video production.
BLOCKED_PATTERNS = (
    r"rm\s+-rf\s+/(?:\s|$)",
    r"\brm\s+-rf\s+~",
    r"\bformat\s+[a-zA-Z]:",
    r"\bdiskpart\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\s*\{.*\}\s*;\s*:",
    r"Remove-Item\s+.*-Recurse.*\b[a-zA-Z]:\\?\s*$",
    r"\bdel\s+/[sfq]\b.*[a-zA-Z]:\\",
)


class EventEmitter:
    """Small helper for Open WebUI status events (progress in the chat UI)."""

    def __init__(self, event_emitter: Optional[Callable[[dict], Any]] = None):
        self.event_emitter = event_emitter

    async def status(self, description: str, done: bool = False) -> None:
        if not self.event_emitter:
            return
        try:
            await self.event_emitter(
                {"type": "status", "data": {"description": description, "done": done}}
            )
        except Exception:
            # Never let UI plumbing break a tool call.
            pass


class Tools:
    class Valves(BaseModel):
        project_root: str = Field(
            default="",
            description=(
                "Absolute path to your OpenMontage clone, e.g. C:\\OpenMontage "
                "or /home/you/OpenMontage. Leave empty to use the "
                "OPENMONTAGE_ROOT environment variable."
            ),
        )
        timeout_seconds: int = Field(
            default=600,
            description="Default per-command timeout. Renders need minutes.",
        )
        max_output_chars: int = Field(
            default=6000,
            description="Trim command output to this many characters before returning it to the model.",
        )
        confirm_commands: bool = Field(
            default=False,
            description="Ask for confirmation in the UI before running each shell command (recommended on shared instances).",
        )
        extra_blocked_patterns: str = Field(
            default="",
            description="Additional regexes to refuse, one per line.",
        )

    def __init__(self):
        self.valves = self.Valves()

    # -- helpers -----------------------------------------------------------

    def _root(self) -> Path:
        raw = (self.valves.project_root or os.environ.get("OPENMONTAGE_ROOT") or "").strip()
        if not raw:
            raise ValueError(
                "Set the OpenMontage tool's `project_root` valve to your clone "
                "(for example C:\\OpenMontage), or export OPENMONTAGE_ROOT."
            )
        root = Path(raw).expanduser()
        if not root.is_dir():
            raise ValueError(f"project_root does not exist: {root}")
        return root.resolve()

    def _checkout_problems(self, root: Path) -> list[str]:
        return [rel for rel in CHECKOUT_FILES if not (root / rel).exists()]

    def _resolve(self, relative: str) -> Path:
        """Resolve a path and refuse anything that escapes the project folder."""
        root = self._root()
        candidate = Path(relative)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(
                f"Path escapes the project folder: {relative} (allowed: {root})"
            )
        return resolved

    def _shell_command(self, command: str) -> list[str]:
        if os.name == "nt":
            return [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ]
        shell = os.environ.get("SHELL") or "/bin/bash"
        return [shell, "-lc", command]

    def _check_blocked(self, command: str) -> Optional[str]:
        patterns = list(BLOCKED_PATTERNS)
        for line in (self.valves.extra_blocked_patterns or "").splitlines():
            line = line.strip()
            if line:
                patterns.append(line)
        for pattern in patterns:
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    return pattern
            except re.error:
                continue
        return None

    def _trim(self, text: str) -> str:
        limit = max(500, int(self.valves.max_output_chars))
        if len(text) <= limit:
            return text
        head = text[: limit // 2]
        tail = text[-limit // 2:]
        return f"{head}\n\n... [trimmed {len(text) - limit} characters] ...\n\n{tail}"

    async def _run(self, command: str, timeout_seconds: int) -> tuple[int, str]:
        """Run a command in the project root, returning (returncode, output)."""
        root = self._root()
        argv = self._shell_command(command)

        async def _spawn() -> tuple[int, str]:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await proc.communicate()
            return proc.returncode or 0, (out or b"").decode("utf-8", "replace")

        try:
            return await asyncio.wait_for(_spawn(), timeout=timeout_seconds)
        except NotImplementedError:
            # e.g. a SelectorEventLoop on Windows — fall back to a thread.
            return await asyncio.to_thread(self._run_blocking, argv, root, timeout_seconds)
        except asyncio.TimeoutError:
            return 124, (
                f"[timeout after {timeout_seconds}s] The command was still running. "
                "Renders can take minutes — retry with a larger timeout_seconds, "
                "or run the render in the background and poll for the output file."
            )

    def _run_blocking(self, argv: list[str], root: Path, timeout_seconds: int) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                argv,
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return 124, f"[timeout after {timeout_seconds}s]"
        except OSError as exc:
            return 127, f"could not start command: {exc}"
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    # -- tool methods (the model reads these docstrings) -------------------

    async def om_status(self) -> str:
        """
        Report the state of the OpenMontage install: project folder, git branch, whether
        the Python and Node dependencies are present, and the toolchain versions
        (Python, Node, npm, ffmpeg). Call this first in a new chat.

        :return: A short status report.
        """
        try:
            root = self._root()
        except ValueError as exc:
            return f"Error: {exc}"

        lines = [f"Project: {root}", f"Backend Python: {sys.executable}"]
        problems = self._checkout_problems(root)
        lines.append(
            "Checkout: complete"
            if not problems
            else "Checkout: PROBLEM — missing " + ", ".join(problems)
        )
        lines.append(
            ".env: " + ("present" if (root / ".env").exists() else "missing (run setup)")
        )
        lines.append(
            "Remotion deps: "
            + (
                "installed"
                if (root / "remotion-composer" / "node_modules").exists()
                else "missing (run: npm install, inside remotion-composer)"
            )
        )

        for label, command in (
            ("git", "git rev-parse --abbrev-ref HEAD"),
            ("python", "python --version"),
            ("node", "node --version"),
            ("npm", "npm --version"),
            ("ffmpeg", "ffmpeg -version"),
        ):
            code, out = await self._run(command, 30)
            first = (out or "").strip().splitlines()[0] if out.strip() else "(no output)"
            lines.append(f"{label}: {first if code == 0 else 'NOT AVAILABLE — ' + first[:120]}")
        return "\n".join(lines)

    async def om_run_command(
        self,
        command: str,
        timeout_seconds: int = 0,
        __event_emitter__: Optional[Callable[[dict], Any]] = None,
        __event_call__: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """
        Run ONE shell command inside the OpenMontage project folder and return its output.
        Use this to run setup, tests, pipeline scripts, and ffprobe checks.

        Keep it to a single command per call — do not chain with `&&` (it is a parse
        error in Windows PowerShell 5.1). If a command needs a different folder, use
        `cd <folder>` inside the command string.

        :param command: The command to run, e.g. `python scripts/setup.py --check-only`
            or `ffprobe -v error -show_entries format=duration -of default=nw=1 out.mp4`.
        :param timeout_seconds: Override the timeout for long renders (0 = use the default).
        :return: The command output (trimmed), plus the exit code.
        """
        emitter = EventEmitter(__event_emitter__)
        blocked = self._check_blocked(command)
        if blocked:
            return (
                f"Refused: this command matches a blocked pattern ({blocked}). "
                "Ask the user to run it manually if it is genuinely needed."
            )

        if self.valves.confirm_commands and __event_call__:
            try:
                approved = await __event_call__(
                    {
                        "type": "confirmation",
                        "data": {
                            "title": "Run this command?",
                            "message": command,
                        },
                    }
                )
            except Exception:
                approved = False
            if not approved:
                return "Cancelled: the user declined to run the command."

        timeout = int(timeout_seconds) or int(self.valves.timeout_seconds)
        await emitter.status(f"$ {command}")
        try:
            code, output = await self._run(command, timeout)
        except ValueError as exc:
            return f"Error: {exc}"
        await emitter.status(f"exit {code}", done=True)
        return f"exit code: {code}\n{self._trim(output.strip()) or '(no output)'}"

    async def om_read_file(self, path: str, max_lines: int = 0) -> str:
        """
        Read a text file from the project (for example AGENT_GUIDE.md, a pipeline
        manifest, a stage skill, or a produced script). Always read AGENT_GUIDE.md
        before starting production work.

        :param path: Path relative to the project root, e.g. `AGENT_GUIDE.md`.
        :param max_lines: Return only the first N lines (0 = whole file).
        :return: The file contents, or an error message.
        """
        try:
            target = self._resolve(path)
        except ValueError as exc:
            return f"Error: {exc}"
        if not target.exists():
            return f"Error: no such file: {target}"
        if target.is_dir():
            return f"Error: {target} is a directory — use om_list_files."
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Error reading {target}: {exc}"
        if max_lines and max_lines > 0:
            text = "\n".join(text.splitlines()[:max_lines])
        return self._trim(text)

    async def om_write_file(self, path: str, content: str) -> str:
        """
        Write a text file inside the project (creates parent folders). Use this for
        notes, briefs, or config the user asked you to save — not for generated media.

        :param path: Path relative to the project root, e.g. `projects/my-video/brief.md`.
        :param content: Full file contents to write.
        :return: Confirmation with the byte count, or an error message.
        """
        try:
            target = self._resolve(path)
        except ValueError as exc:
            return f"Error: {exc}"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return f"Error writing {target}: {exc}"
        return f"Wrote {len(content.encode('utf-8'))} bytes to {target}"

    async def om_list_files(
        self, path: str = ".", pattern: str = "*", max_entries: int = 200
    ) -> str:
        """
        List files in the project, optionally filtered by glob pattern. Useful for
        finding pipeline manifests (pipeline_defs/*.yaml), stage skills
        (skills/pipelines/**/*.md), and rendered output (projects/**/*.mp4).

        :param path: Folder relative to the project root (default: project root).
        :param pattern: Glob pattern, e.g. `*.yaml` or `**/*.mp4`.
        :param max_entries: Cap the number of entries listed.
        :return: One path per line, or an error message.
        """
        try:
            base = self._resolve(path)
        except ValueError as exc:
            return f"Error: {exc}"
        if not base.exists():
            return f"Error: no such folder: {base}"
        entries = sorted(base.glob(pattern)) if pattern else sorted(base.iterdir())
        if not entries:
            return f"No matches for {pattern!r} in {base}"
        shown = entries[: max(1, max_entries)]
        lines = [
            f"{p.relative_to(self._root())}{'/' if p.is_dir() else ''}" for p in shown
        ]
        if len(entries) > len(shown):
            lines.append(f"... {len(entries) - len(shown)} more")
        return self._trim("\n".join(lines))

    async def om_preflight(self) -> str:
        """
        Run OpenMontage's provider-menu preflight and return the compact JSON summary:
        which composition runtimes work (ffmpeg / Remotion / HyperFrames), how many
        providers are configured per capability, and which tools are one API key away
        from working. Run this before proposing a production plan, then tell the user
        what they have and what one key would unlock.

        :return: The provider menu summary JSON (trimmed), or an error message.
        """
        try:
            self._root()
        except ValueError as exc:
            return f"Error: {exc}"

        last_error = ""
        for interpreter in _interpreter_candidates():
            code, output = await self._run(
                f'"{interpreter}" -c "{PREFLIGHT_CODE}"', 180
            )
            if code == 0:
                try:
                    menu = json.loads(output)
                except json.JSONDecodeError:
                    return self._trim(output.strip())
                return self._trim(json.dumps(menu))
            last_error = output.strip() or f"exit {code}"

        return (
            "Preflight failed on every Python interpreter I tried "
            f"({', '.join(_interpreter_candidates())}). The repo's Python "
            "dependencies are probably not installed yet — run "
            "`python scripts/setup.py`. Last output:\n"
            + self._trim(last_error)
        )
