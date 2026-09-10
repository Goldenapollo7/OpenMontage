<#
.SYNOPSIS
    OpenMontage setup for Windows PowerShell (5.1 and 7+).

.DESCRIPTION
    Thin wrapper around scripts\setup.py, which does the actual work and is
    shared with macOS/Linux (`make setup` calls the same file).

    Nothing here uses `&&` or any other PowerShell 7-only syntax, so it runs on
    the PowerShell 5.1 that ships with Windows 10/11.

.EXAMPLE
    .\setup.ps1
    .\setup.ps1 --check-only
    .\setup.ps1 --skip-piper

.NOTES
    If Windows refuses to run this file ("running scripts is disabled on this
    system"), either run:

        powershell -ExecutionPolicy Bypass -File .\setup.ps1

    or use setup.cmd instead.
#>

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SetupArgs
)

# Do not use 'Stop' here: probing candidate interpreters can write to stderr,
# and this wrapper makes its own explicit exit-code decisions.
$ErrorActionPreference = 'Continue'

# Always operate from the repo root, whatever the shell's current directory is.
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RepoRoot

function Test-PythonCandidate {
    param([string]$Exe, [string[]]$PreArgs)

    # Skip the Microsoft Store alias — it opens the Store instead of running
    # Python, which looks like an infinite hang to the user.
    if ($Exe -like '*\WindowsApps\*') {
        Write-Host "  [!!] Skipping the Microsoft Store alias for python: $Exe" -ForegroundColor Yellow
        Write-Host '       Install Python from https://www.python.org/downloads/ and tick'
        Write-Host '       "Add python.exe to PATH".'
        return $false
    }

    if (-not (Test-Path -LiteralPath $Exe)) { return $false }

    $probe = 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
    & $Exe @PreArgs -c $probe 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Find-PythonLauncher {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py -and (Test-PythonCandidate -Exe $py.Source -PreArgs @('-3'))) {
        return @($py.Source, '-3')
    }
    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and (Test-PythonCandidate -Exe $cmd.Source -PreArgs @())) {
            return @($cmd.Source)
        }
    }
    return $null
}

Write-Host 'OpenMontage setup (Windows)' -ForegroundColor Cyan
Write-Host "  repo: $RepoRoot"

$launcher = Find-PythonLauncher
if (-not $launcher) {
    Write-Host ''
    Write-Host '  [xx]  Python 3.10+ was not found on PATH.' -ForegroundColor Red
    Write-Host '        Install it from https://www.python.org/downloads/ and tick'
    Write-Host '        "Add python.exe to PATH", then run this script again.'
    Write-Host '        Already installed? Close and reopen your terminal so PATH refreshes.'
    exit 1
}

$exe = $launcher[0]
$preArgs = @()
if ($launcher.Count -gt 1) { $preArgs = $launcher[1..($launcher.Count - 1)] }

& $exe @preArgs 'scripts\setup.py' @SetupArgs
$rc = $LASTEXITCODE
if ($null -eq $rc) { $rc = 0 }

if ($rc -ne 0) {
    Write-Host ''
    Write-Host "  Setup exited with code $rc. Re-run with --check-only for details:" -ForegroundColor Yellow
    Write-Host '    python scripts\setup.py --check-only'
}
exit $rc
