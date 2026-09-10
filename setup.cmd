@echo off
REM ---------------------------------------------------------------------------
REM OpenMontage setup for Windows (CMD / double-click).
REM
REM Thin wrapper around scripts\setup.py - the same script `make setup` calls on
REM macOS/Linux. No shell chaining tricks, no PowerShell required.
REM
REM Usage (from a terminal):
REM     setup.cmd
REM     setup.cmd --check-only
REM     setup.cmd --skip-piper
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PY="

REM Prefer the py launcher, then plain python on PATH. Each candidate must
REM actually import sys and be >= 3.10 - otherwise we keep looking.
where py >nul 2>nul && py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"

if not defined PY (
  where python >nul 2>nul && python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
)

if not defined PY (
  where python3 >nul 2>nul && python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python3"
)

if not defined PY (
  echo.
  echo   [xx]  Python 3.10+ was not found on PATH.
  echo         Install it from https://www.python.org/downloads/ and tick
  echo         "Add python.exe to PATH", then run setup.cmd again.
  echo         Already installed? Close and reopen this window so PATH refreshes.
  echo.
  pause
  exit /b 1
)

echo OpenMontage setup (Windows^)
echo   python: %PY%
echo.

%PY% scripts\setup.py %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :failed

exit /b 0

:failed
echo.
echo   Setup exited with code %RC%. Re-run with --check-only for details:
echo     python scripts\setup.py --check-only
echo.
pause
exit /b %RC%
