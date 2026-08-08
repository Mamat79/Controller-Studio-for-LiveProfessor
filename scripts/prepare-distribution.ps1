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
Copy-Item -LiteralPath (Join-Path $ProjectRoot "CHANGELOG.md") -Destination $staging
Copy-Item -LiteralPath (Join-Path $ProjectRoot "config.example.json") -Destination $staging
$publicDocs = @(
    "CARTOGRAPHIE_MIDI_SYSEX.md",
    "CONFIGURATION_EC4.md",
    "GUIDE_INSTALLATION_UTILISATION.md",
    "RAPPORT_STABILISATION_UI_UPDATER_V0.5.0.md",
    "SOURCES.md"
)
$publicDocsDestination = Join-Path $staging "docs"
New-Item -ItemType Directory -Path $publicDocsDestination -Force | Out-Null
foreach ($document in $publicDocs) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs\$document") -Destination $publicDocsDestination
}
$englishDocsSource = Join-Path $ProjectRoot "docs\en"
if (Test-Path -LiteralPath $englishDocsSource -PathType Container) {
    Copy-Item -LiteralPath $englishDocsSource -Destination (Join-Path $publicDocsDestination "en") -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $ProjectRoot "profiles") -Destination (Join-Path $staging "profiles") -Recurse -Force

foreach ($controllerName in @("Ec4-UniBank.ctrl2", "Ec4-FullBank.ctrl2")) {
    $controllerPath = Join-Path $ProjectRoot $controllerName
    if (-not (Test-Path -LiteralPath $controllerPath -PathType Leaf)) {
        throw "Fichier contrôleur introuvable : $controllerPath"
    }
    Copy-Item -LiteralPath $controllerPath -Destination $staging -Force
}
if ($ControllerFile) {
    Write-Warning "-ControllerFile n'est plus nécessaire : les modèles UniBank et FullBank officiels sont inclus automatiquement."
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Package prêt : $zipPath"
