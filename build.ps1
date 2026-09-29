$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Run: py -3.12 -m venv .venv"
}

& $Python (Join-Path $ProjectRoot "tools\generate_icon.py") (Join-Path $ProjectRoot "assets\codex_usage_pet.ico")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m PyInstaller --clean --noconfirm (Join-Path $ProjectRoot "packaging\CodexUsagePet.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$DistRoot = Join-Path $ProjectRoot "dist\RitaDesktopPet"
Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE") -Destination $DistRoot -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination $DistRoot -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "RELEASE_NOTES_v0.1.0-beta.md") -Destination $DistRoot -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "GITHUB_RELEASE_UPLOAD.md") -Destination $DistRoot -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "THIRD_PARTY_NOTICES.md") -Destination $DistRoot -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSES") -Destination $DistRoot -Recurse -Force

$Archive = Join-Path $ProjectRoot "dist\Rita-Desktop-Pet-v0.1.0-beta-portable.zip"
Compress-Archive -LiteralPath $DistRoot -DestinationPath $Archive -CompressionLevel Optimal -Force
exit $LASTEXITCODE

