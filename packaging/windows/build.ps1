[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$spec = Join-Path $PSScriptRoot 'SiLeMIO-Controller-Studio.spec'

Push-Location $projectRoot
try {
    python -m PyInstaller --noconfirm --clean $spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller a échoué avec le code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$output = Join-Path $projectRoot 'dist\Controller-Studio-for-LiveProfessor.exe'
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw "Exécutable attendu introuvable : $output"
}
Get-FileHash -Algorithm SHA256 -LiteralPath $output
