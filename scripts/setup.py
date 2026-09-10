#!/usr/bin/env python3
"""OpenMontage one-command setup — works on Windows, macOS, and Linux.

This is the cross-platform replacement for the old README fallback one-liner::

    pip install -r requirements.txt && cd remotion-composer && npm install && ...

That chain only works in bash/zsh. On Windows PowerShell 5.1 (the version that
ships with Windows 10/11) ``&&`` is a parser error — "The token '&&' is not a
valid statement separator in this version" — and ``cp``/``cd`` semantics differ
too. Every step here is spawned as its own process, so nothing depends on the
shell the user happens to be sitting in.

Usage::

    python scripts/setup.py              # full setup (any OS, any shell)
    python scripts/setup.py --check-only # diagnose the toolchain, install nothing
    python scripts/setup.py --dry-run    # print the commands without running them

``make setup`` on macOS/Linux simply calls this script, so the two paths cannot
drift apart. Flags let users skip individual pieces (``--skip-npm``,
``--skip-piper``, ``--skip-hyperframes``, ``--skip-env``).

Exit code is 0 when every required step succeeded. Optional steps (Piper TTS,
the HyperFrames cache warm, ``.env`` creation) may fail without failing setup —
they are reported in the summary instead.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSER_DIR = REPO_ROOT / "remotion-composer"
ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# Files that only exist in a real clone — used to tell "wrong directory" apart
# from "broken install".
CHECKOUT_FILES = (
    "requirements.txt",
    "remotion-composer/package.json",
    ".env.example",
)

PYTHON_FLOOR = (3, 10)          # README prerequisite
REMOTION_NODE_FLOOR = 18        # README prerequisite ("Node.js 18+")
HYPERFRAMES_NODE_FLOOR = 22     # tools/video/hyperframes_compose.py::_NODE_FLOOR_MAJOR

IS_WINDOWS = os.name == "nt"

# Status values used by both the live log and the final summary.
OK = "ok"
SKIP = "skip"
WARN = "warn"
FAIL = "fail"


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def _prepare_stdout() -> None:
    """Make stdout resilient on Windows consoles.

    Legacy Windows code pages (cp1252/cp437) cannot encode the output some
    installers print, which would otherwise kill setup with a
    UnicodeEncodeError in the middle of a long install.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _emit(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:  # pragma: no cover - legacy Windows console
        encoding = sys.stdout.encoding or "utf-8"
        print(text.encode(encoding, "replace").decode(encoding, "replace"))


def _header(title: str) -> None:
    _emit()
    _emit(f"==> {title}")


def _line(status: str, text: str) -> None:
    marker = {OK: "  [ok]  ", SKIP: "  [--]  ", WARN: "  [!!]  ", FAIL: "  [xx]  "}[status]
    _emit(f"{marker}{text}")


def _note(text: str) -> None:
    _emit(f"        {text}")


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------

def _resolve_executable(name: str) -> str | None:
    """Resolve a command name, including Windows ``.cmd``/``.bat`` wrappers.

    Mirrors ``BaseTool.run_command`` so that ``npm``/``npx`` found on PATH as
    ``npm.CMD`` work without ``shell=True``.
    """
    return shutil.which(name)


def _format_cmd(cmd: list[str]) -> str:
    parts = [f'"{c}"' if " " in c else c for c in cmd]
    return " ".join(parts)


@dataclass
class CommandResult:
    returncode: int
    output: str = ""


def run_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    dry_run: bool = False,
    stream: bool = True,
) -> CommandResult:
    """Run ``cmd``, streaming output live and keeping the tail for errors.

    Return codes are never raised — the caller decides what a failure means,
    which is what makes "optional step" handling possible.
    """
    location = f"   (in {cwd})" if cwd and cwd != REPO_ROOT else ""
    _emit(f"      $ {_format_cmd(cmd)}{location}")
    if dry_run:
        return CommandResult(0, "")

    resolved = list(cmd)
    if resolved:
        exe = _resolve_executable(resolved[0])
        if exe:
            resolved[0] = exe

    try:
        proc = subprocess.Popen(
            resolved,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        return CommandResult(127, f"could not start {resolved[0]}: {exc}")

    tail: list[str] = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        text = raw.rstrip()
        tail = (tail + [text])[-20:]  # keep the last 20 lines for error reports
        if stream:
            _emit(f"        | {text}")
    returncode = proc.wait()
    return CommandResult(returncode, "\n".join(tail))


def _run_version(cmd: list[str]) -> str | None:
    """Return the first line of ``cmd --version`` output, or None on failure."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    text = (proc.stdout or proc.stderr or "").strip()
    return text.splitlines()[0].strip() if text else None


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

@dataclass
class Step:
    key: str
    title: str
    required: bool = True
    status: str = SKIP
    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.status == FAIL


@dataclass
class Setup:
    dry_run: bool = False
    steps: dict[str, Step] = field(default_factory=dict)

    def step(self, key: str, title: str, *, required: bool = True) -> Step:
        s = Step(key=key, title=title, required=required)
        self.steps[key] = s
        return s

    # -- preflight ---------------------------------------------------------

    def missing_checkout_files(self) -> list[str]:
        """Repo-relative paths that a complete OpenMontage checkout must have.

        Catches the most common Windows support report: commands pasted into a
        terminal that is not sitting in the cloned project (``C:\\WINDOWS\\system32``
        is a favorite), and zip downloads or partial clones.
        """
        return [
            rel for rel in CHECKOUT_FILES if not (REPO_ROOT / rel).exists()
        ]

    def preflight(self) -> None:
        _header("Checking your toolchain")
        s = self.step("preflight", "Toolchain check")

        missing = self.missing_checkout_files()
        if missing:
            _line(FAIL, "This does not look like a complete OpenMontage checkout")
            _note(f"setup is looking at: {REPO_ROOT}")
            for rel in missing:
                _note(f"missing: {REPO_ROOT / rel}")
            _note("If that path is not where you cloned the project, run setup "
                  "from the clone (the folder containing README.md and "
                  "requirements.txt):")
            _note("  cd C:\\OpenMontage        # or wherever you cloned it")
            _note("  python scripts\\setup.py")
            _note("Not cloned yet?")
            _note("  git clone https://github.com/calesthio/OpenMontage.git "
                  "C:\\OpenMontage")
            s.status = FAIL
            s.detail = f"missing {', '.join(missing)}"
            return

        py = platform.python_version()
        if sys.version_info[:2] >= PYTHON_FLOOR:
            _line(OK, f"Python {py} ({sys.executable})")
        else:
            floor = ".".join(str(p) for p in PYTHON_FLOOR)
            _line(FAIL, f"Python {py} is too old — OpenMontage needs {floor}+")
            _note("Install a newer Python: https://www.python.org/downloads/")
            s.status = FAIL
            s.detail = f"Python {py} < {floor}"
            return

        pip_ok = _run_version([sys.executable, "-m", "pip", "--version"])
        if pip_ok:
            _line(OK, f"pip — {pip_ok}")
        else:
            _line(FAIL, "pip is not available for this Python")
            _note("Fix with: python -m ensurepip --upgrade")
            s.status = FAIL
            s.detail = "pip missing"
            return

        node = _resolve_executable("node")
        node_major = None
        if node:
            raw = _run_version([node, "--version"]) or ""
            node_major = _major_version(raw)
            if node_major is None:
                _line(WARN, "node found but its version could not be read")
            elif node_major < REMOTION_NODE_FLOOR:
                _line(FAIL, f"Node.js {raw} is too old — Remotion needs "
                            f"{REMOTION_NODE_FLOOR}+")
                _note("Install Node.js 18+ (LTS recommended): https://nodejs.org/")
            elif node_major < HYPERFRAMES_NODE_FLOOR:
                _line(WARN, f"Node.js {raw} — Remotion is fine, but HyperFrames "
                            f"needs {HYPERFRAMES_NODE_FLOOR}+")
            else:
                _line(OK, f"Node.js {raw}")
        else:
            _line(FAIL, "Node.js not found on PATH")
            _note("Install Node.js 18+: https://nodejs.org/  "
                  "(Windows: `winget install OpenJS.NodeJS.LTS`)")
            _note("Then reopen your terminal so PATH is refreshed.")

        for name, hint in (
            ("npm", "comes with Node.js"),
            ("npx", "comes with Node.js"),
        ):
            if _resolve_executable(name):
                _line(OK, f"{name} found")
            else:
                _line(WARN, f"{name} not found on PATH ({hint})")

        ffmpeg = _resolve_executable("ffmpeg")
        if ffmpeg:
            _line(OK, f"ffmpeg — {_run_version([ffmpeg, '-version']) or ffmpeg}")
        else:
            _line(WARN, "ffmpeg not found on PATH — rendering and audio muxing "
                        "need it")
            _note(_ffmpeg_hint())

        if os.name == "nt":
            self._windows_warnings()

        if node is None or node_major is None or node_major < REMOTION_NODE_FLOOR:
            s.status = FAIL
            s.detail = "Node.js 18+ required for the Remotion composer"
        else:
            s.status = OK

    def _windows_warnings(self) -> None:
        """Warn about Windows-specific traps that break npm/Remotion builds."""
        exe = sys.executable or ""
        if "WindowsApps" in exe:
            _line(WARN, "This is the Microsoft Store build of Python")
            _note("It is sandboxed and often breaks pip installs. Prefer the "
                  "python.org installer with \"Add python.exe to PATH\".")
        path = str(REPO_ROOT)
        if " " in path:
            _line(WARN, "The project path contains spaces")
            _note(f"  {path}")
            _note("npm/Remotion/ffmpeg toolchains choke on that. Cloning to "
                  "C:\\OpenMontage avoids a long class of weird failures.")
        if any(ord(ch) > 127 for ch in path):
            _line(WARN, "The project path contains non-ASCII characters")
            _note("Some Node.js build tools cannot read non-ASCII paths; "
                  "C:\\OpenMontage is safer.")

    # -- dependency installs ----------------------------------------------

    def install_python_deps(self) -> None:
        _header("Installing Python dependencies (requirements.txt)")
        s = self.step("pip", "Python dependencies")
        res = run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=REPO_ROOT,
            dry_run=self.dry_run,
        )
        if res.returncode == 0:
            _line(OK, "Python packages installed")
            s.status = OK
        else:
            pepped = "externally-managed-environment" in res.output
            _line(FAIL, "pip refused to install the dependencies" if pepped
                        else "pip install failed")
            if pepped:
                _note("This Python is managed by the OS (PEP 668), which is the "
                      "default on modern Debian/Ubuntu. Use a virtual "
                      "environment instead:")
            else:
                _note("Common fixes: upgrade pip (`python -m pip install "
                      "--upgrade pip`), or install into a virtual environment:")
            _note("  python -m venv .venv")
            _note("  Windows:        .venv\\Scripts\\python scripts\\setup.py")
            _note("  macOS / Linux:  .venv/bin/python scripts/setup.py")
            s.status = FAIL
            s.detail = res.output.splitlines()[-1] if res.output else "pip failed"

    def install_remotion(self) -> None:
        _header("Installing the Remotion composer (remotion-composer/)")
        s = self.step("npm", "Remotion composer")

        if not COMPOSER_DIR.is_dir():
            _line(FAIL, f"{COMPOSER_DIR} is missing — is this a full clone?")
            s.status = FAIL
            s.detail = "remotion-composer/ not found"
            return

        if not _resolve_executable("npm"):
            _line(FAIL, "npm not found — install Node.js 18+ and reopen the "
                        "terminal: https://nodejs.org/")
            s.status = FAIL
            s.detail = "npm missing"
            return

        res = run_command(["npm", "install"], cwd=COMPOSER_DIR,
                          dry_run=self.dry_run)
        if res.returncode != 0:
            # Documented Windows workaround: npm occasionally fails with
            # ERR_INVALID_ARG_TYPE; the npx-shipped npm copy usually succeeds.
            _line(WARN, "npm install failed — retrying with `npx --yes npm "
                        "install` (the documented fallback)")
            res = run_command(["npx", "--yes", "npm", "install"], cwd=COMPOSER_DIR,
                              dry_run=self.dry_run)

        if res.returncode == 0:
            _line(OK, "Remotion composer ready")
            s.status = OK
        else:
            _line(FAIL, "npm install failed twice")
            _note("Try by hand, one command per line:")
            _note("  cd remotion-composer")
            _note("  npx --yes npm install")
            _note("If you are offline, reconnect and re-run setup.")
            s.status = FAIL
            s.detail = "npm install failed"

    def install_piper(self) -> None:
        _header("Installing free offline TTS (Piper)")
        s = self.step("piper", "Piper TTS (offline narration)", required=False)
        res = run_command(
            [sys.executable, "-m", "pip", "install", "piper-tts"],
            cwd=REPO_ROOT,
            dry_run=self.dry_run,
        )
        if res.returncode == 0:
            _line(OK, "Piper TTS installed — free offline narration available")
            s.status = OK
        else:
            _line(SKIP, "piper-tts did not install (optional)")
            _note("Piper has no wheel for every Python/OS combination. Cloud TTS "
                  "providers (ElevenLabs, Google, OpenAI) and other free paths "
                  "still work — nothing else is affected.")
            s.status = SKIP

    def warm_hyperframes(self) -> None:
        _header("Warming the HyperFrames runtime (npx cache)")
        s = self.step("hyperframes", "HyperFrames runtime", required=False)
        npx = _resolve_executable("npx")
        if not npx:
            _line(SKIP, "npx not found — skipping (Remotion rendering unaffected)")
            s.status = SKIP
            return

        _note("Pulls the `hyperframes` npm package into the local npx cache so "
              "the first render doesn't pay a cold-fetch penalty (~20MB).")
        res = run_command(["npx", "--yes", "hyperframes", "--version"],
                          cwd=REPO_ROOT, dry_run=self.dry_run, stream=False)
        if res.returncode != 0:
            _line(SKIP, "cache warm failed — offline or npm unavailable")
            _note("Not fatal: the first HyperFrames render will fetch it on "
                  "demand. Re-run setup later (or `make hyperframes-warm` on "
                  "macOS/Linux) to warm the cache.")
            s.status = SKIP
            return

        _line(OK, "HyperFrames CLI cached")
        self._report_hyperframes_status()
        s.status = OK

    def _report_hyperframes_status(self) -> None:
        """Print the runtime probe from the repo's own tool, if importable."""
        if self.dry_run:
            return
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        try:
            from tools.video.hyperframes_compose import HyperFramesCompose
        except Exception as exc:  # pragma: no cover - depends on install state
            _note(f"runtime probe skipped ({type(exc).__name__})")
            return
        try:
            HyperFramesCompose._npm_resolve_cache = None
            check = HyperFramesCompose()._runtime_check()
        except Exception as exc:  # pragma: no cover
            _note(f"runtime probe skipped ({type(exc).__name__})")
            return
        available = check.get("runtime_available")
        version = check.get("npm_package_version") or check.get("npm_resolve_error")
        _line(OK if available else WARN,
              f"HyperFrames runtime_available={available} (npm: {version})")
        for reason in check.get("reasons", []):
            _note(f"note: {reason}")

    def create_env(self) -> None:
        _header("Creating .env")
        s = self.step("env", ".env file", required=False)
        if ENV_FILE.exists():
            _line(OK, ".env already exists — leaving it untouched")
            s.status = OK
            return
        if not ENV_EXAMPLE.exists():
            _line(SKIP, ".env.example not found — skipping")
            s.status = SKIP
            return
        if self.dry_run:
            _line(SKIP, f"would copy {ENV_EXAMPLE.name} -> {ENV_FILE.name}")
            s.status = SKIP
            return
        try:
            shutil.copy(ENV_EXAMPLE, ENV_FILE)
        except OSError as exc:
            _line(WARN, f"could not create .env: {exc}")
            s.status = WARN
            return
        _line(OK, "Created .env from .env.example")
        _note("Every key is optional — add what you have and more tools unlock.")
        s.status = OK

    # -- reporting ---------------------------------------------------------

    def summary(self) -> int:
        required_failed = [s for s in self.steps.values()
                           if s.required and s.failed]
        optional_skipped = [s for s in self.steps.values()
                            if not s.required and s.status in (SKIP, WARN, FAIL)]

        _header("Summary")
        for s in self.steps.values():
            label = {"ok": OK, "skip": SKIP, "warn": WARN, "fail": FAIL}.get(
                s.status, SKIP)
            suffix = "" if s.required else " (optional)"
            _line(label, f"{s.title}{suffix}")
            if s.detail:
                _note(s.detail)

        _emit()
        if required_failed:
            _emit("Setup finished with problems:")
            for s in required_failed:
                _emit(f"  - {s.title}: {s.detail or 'failed'}")
            _emit()
            _emit("Re-run `python scripts/setup.py --check-only` to see which "
                  "tool is missing.")
            return 1

        _emit("Done! Open this project in your AI coding assistant and start "
              "creating.")
        _emit("  Try: \"Make a 60-second animated explainer about how neural "
              "networks learn\"")
        if optional_skipped:
            _emit("  Optional pieces were skipped: "
                  + ", ".join(s.title for s in optional_skipped))
        _emit("  Optional: add API keys to .env to unlock cloud providers.")
        if not IS_WINDOWS:
            _emit("  Optional: run `make install-gpu` if you have an NVIDIA GPU.")
            _emit("  Optional: run `make hyperframes-doctor` to fully validate "
                  "the HyperFrames runtime.")
        else:
            _emit("  Optional: `python scripts\\setup.py --check-only` re-checks "
                  "your toolchain any time.")
        return 0


def _major_version(raw: str) -> int | None:
    """Extract the major version from strings like ``v22.22.3`` or ``16.20.2``."""
    cleaned = raw.strip().lstrip("vV")
    head = cleaned.split(".")[0]
    return int(head) if head.isdigit() else None


def _ffmpeg_hint() -> str:
    system = platform.system()
    if system == "Windows":
        return ("Install with `winget install ffmpeg` (or `choco install ffmpeg`), "
                "then reopen the terminal.")
    if system == "Darwin":
        return "Install with `brew install ffmpeg`."
    return "Install with `sudo apt install ffmpeg` (or your distro's package manager)."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python scripts/setup.py",
        description="Set up OpenMontage on Windows, macOS, or Linux.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/setup.py                 full setup\n"
            "  python scripts/setup.py --check-only    diagnose only\n"
            "  python scripts/setup.py --dry-run       show every command\n"
        ),
    )
    parser.add_argument("--check-only", action="store_true",
                        help="check the toolchain and exit without installing")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the commands that would run, execute nothing")
    parser.add_argument("--skip-npm", action="store_true",
                        help="skip `npm install` for the Remotion composer")
    parser.add_argument("--skip-piper", action="store_true",
                        help="skip the free offline Piper TTS install")
    parser.add_argument("--skip-hyperframes", action="store_true",
                        help="skip the HyperFrames npx cache warm")
    parser.add_argument("--skip-env", action="store_true",
                        help="skip creating .env from .env.example")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _prepare_stdout()

    _emit("OpenMontage setup")
    _emit(f"  repo:    {REPO_ROOT}")
    _emit(f"  python:  {sys.version.split()[0]} ({sys.executable})")
    _emit(f"  os:      {platform.system()} {platform.release()}")
    if args.dry_run:
        _emit("  mode:    DRY RUN — nothing will be installed")

    setup = Setup(dry_run=args.dry_run)
    setup.preflight()

    if args.check_only:
        failed = [s for s in setup.steps.values() if s.failed]
        _emit()
        if failed:
            _emit("Missing or unusable:")
            for s in failed:
                _emit(f"  - {s.title}: {s.detail or 'failed'}")
            return 1
        _emit("Toolchain looks good. Run `python scripts/setup.py` to install "
              "dependencies.")
        return 0

    setup.install_python_deps()
    if args.skip_npm:
        setup.step("npm", "Remotion composer")
        _line(SKIP, "npm install skipped (--skip-npm)")
    else:
        setup.install_remotion()
    if args.skip_piper:
        setup.step("piper", "Piper TTS (offline narration)", required=False)
        _line(SKIP, "piper-tts skipped (--skip-piper)")
    else:
        setup.install_piper()
    if args.skip_hyperframes:
        setup.step("hyperframes", "HyperFrames runtime", required=False)
        _line(SKIP, "HyperFrames cache warm skipped (--skip-hyperframes)")
    else:
        setup.warm_hyperframes()
    if args.skip_env:
        setup.step("env", ".env file", required=False)
        _line(SKIP, ".env creation skipped (--skip-env)")
    else:
        setup.create_env()

    return setup.summary()


if __name__ == "__main__":
    sys.exit(main())
