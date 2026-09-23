$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$Compiler = $Candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

if (-not $Compiler) {
    Write-Error "Inno Setup 6 was not found. Install it, then rerun .\build-installer.ps1."
    exit 2
}

& (Join-Path $ProjectRoot "build.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Compiler (Join-Path $ProjectRoot "packaging\CodexUsagePet.iss")
exit $LASTEXITCODE

