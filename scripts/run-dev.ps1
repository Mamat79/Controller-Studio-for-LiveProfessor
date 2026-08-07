$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment missing."
}

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "src"
    & $Python -m ec4lpbridge
}
finally {
    Pop-Location
}
