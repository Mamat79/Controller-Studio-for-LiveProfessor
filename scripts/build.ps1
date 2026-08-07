$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $ProjectRoot ".venv\Scripts\pyinstaller.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment missing. Create .venv and install requirements-build.txt first."
}

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "src"
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Unit tests failed." }

    & $PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "EC4-LiveProfessor-Bridge" `
        --paths "src" `
        --collect-submodules "mido.backends" `
        --hidden-import "mido.backends.rtmidi" `
        --distpath "output\windows" `
        --workpath "build\pyinstaller" `
        --specpath "build" `
        "launcher.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
}
finally {
    Pop-Location
}
