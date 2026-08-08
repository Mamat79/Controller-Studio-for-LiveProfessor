$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $ProjectRoot ".venv\Scripts\pyinstaller.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment missing. Create .venv and install requirements-build.txt first."
}
$IconPath = Join-Path $ProjectRoot "src\ec4lpbridge\assets\ec4lp.ico"
if (-not (Test-Path -LiteralPath $IconPath)) {
    throw "Icon file missing: $IconPath"
}
$ControllerPath = Join-Path $ProjectRoot "Ec4.ctrl2"
if (-not (Test-Path -LiteralPath $ControllerPath)) {
    throw "LiveProfessor controller file missing: $ControllerPath"
}

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "$ProjectRoot;src"
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Unit tests failed." }

    & $PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --icon "$IconPath" `
        --add-data "$IconPath;ec4lpbridge\\assets" `
        --add-data "$ControllerPath;." `
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
