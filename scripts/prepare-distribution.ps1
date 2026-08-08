param(
    [switch]$NoBuild,
    [string]$OutputRoot = "output\distribution",
    [string]$ControllerFile = ""
)

$ErrorActionPreference = "Stop"
$ScriptRoot = (Resolve-Path $PSScriptRoot).Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..")).Path

if (-not $NoBuild) {
    & (Join-Path $ProjectRoot "scripts\build.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Le build a échoué."
    }
}

$pyproject = Get-Content -LiteralPath (Join-Path $ProjectRoot "pyproject.toml") -Raw
if ($pyproject -notmatch 'version\s*=\s*"([^"]+)"') {
    throw "Version introuvable dans pyproject.toml"
}
$version = $Matches[1]

$exePath = Join-Path $ProjectRoot "output\windows\EC4-LiveProfessor-Bridge.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "EC4-LiveProfessor-Bridge.exe introuvable : lancez scripts\build.ps1"
}

$packageName = "EC4-LiveProfessor-Bridge-v$version-win64"
$packageRoot = Join-Path $ProjectRoot $OutputRoot
$staging = Join-Path $packageRoot $packageName
$zipPath = Join-Path $packageRoot "$packageName.zip"

if (Test-Path -LiteralPath $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging -Force | Out-Null

Copy-Item -LiteralPath $exePath -Destination $staging
Copy-Item -LiteralPath (Join-Path $ProjectRoot "install-ec4-liveprofessor-bridge.ps1") -Destination $staging
Copy-Item -LiteralPath (Join-Path $ProjectRoot "uninstall-ec4-liveprofessor-bridge.ps1") -Destination $staging
Copy-Item -LiteralPath (Join-Path $ProjectRoot "install-ec4-liveprofessor-bridge.bat") -Destination $staging
Copy-Item -LiteralPath (Join-Path $ProjectRoot "uninstall-ec4-liveprofessor-bridge.bat") -Destination $staging
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination $staging
Copy-Item -LiteralPath (Join-Path $ProjectRoot "config.example.json") -Destination $staging
Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs") -Destination (Join-Path $staging "docs") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "profiles") -Destination (Join-Path $staging "profiles") -Recurse -Force

if ($ControllerFile) {
    if (-not (Test-Path -LiteralPath $ControllerFile)) {
        throw "Fichier Ec4.ctrl2 introuvable : $ControllerFile"
    }
    Copy-Item -LiteralPath (Resolve-Path -LiteralPath $ControllerFile).Path -Destination (Join-Path $staging "Ec4.ctrl2") -Force
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Package prêt : $zipPath"
