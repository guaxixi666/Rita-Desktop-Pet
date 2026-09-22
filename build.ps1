$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Run: py -3.12 -m venv .venv"
}

& $Python -m pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m PyInstaller --clean --noconfirm (Join-Path $ProjectRoot "packaging\CodexUsagePet.spec")
exit $LASTEXITCODE

