param(
    [string]$InstallPath = "$env:LOCALAPPDATA\Programs\EC4LiveProfessorBridge",
    [string]$ControllerFile = "",
    [bool]$CreateDesktopShortcut = $true,
    [bool]$CreateStartMenuShortcut = $true,
    [bool]$OverwriteConfig = $false
)

$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[EC4] $Message" -ForegroundColor Cyan
}

function New-Shortcut {
    param(
        [string]$TargetPath,
        [string]$ShortcutPath,
        [string]$Name
    )
    $wscript = New-Object -ComObject WScript.Shell
    $directory = Split-Path -Parent $ShortcutPath
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $link = $wscript.CreateShortcut($ShortcutPath)
    $link.TargetPath = $TargetPath
    $link.WorkingDirectory = Split-Path -Parent $TargetPath
    $link.Description = $Name
    $link.IconLocation = "$TargetPath,0"
    $link.Save()
}

function Get-ScriptSource {
    param([string]$SourceRoot)

    $candidates = @(
        (Join-Path $SourceRoot "EC4-LiveProfessor-Bridge.exe"),
        (Join-Path $SourceRoot "output\windows\EC4-LiveProfessor-Bridge.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Executable EC4-LiveProfessor-Bridge.exe introuvable. Lancez d'abord build.ps1 ou indiquez un dossier contenant l'exe."
}

$sourceRoot = (Resolve-Path (Split-Path -Parent $MyInvocation.MyCommand.Path)).Path
$exePath = Get-ScriptSource -SourceRoot $sourceRoot
$installDir = Join-Path $InstallPath "EC4LiveProfessorBridge"
$targetExe = Join-Path $installDir "EC4-LiveProfessor-Bridge.exe"

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -LiteralPath $exePath -Destination $targetExe -Force
Write-Info "EXE installé dans : $installDir"

$sourceConfig = Join-Path $sourceRoot "config.json"
$portableExample = Join-Path $sourceRoot "config.example.json"
$targetConfig = Join-Path $installDir "config.json"

if ((Test-Path -LiteralPath $sourceConfig -PathType Leaf) -and ((-not (Test-Path -LiteralPath $targetConfig)) -or $OverwriteConfig)) {
    Copy-Item -LiteralPath $sourceConfig -Destination $targetConfig -Force
}
elseif (-not (Test-Path -LiteralPath $targetConfig) -and (Test-Path -LiteralPath $portableExample)) {
    Copy-Item -LiteralPath $portableExample -Destination (Join-Path $installDir "config.example.json") -Force
}

foreach ($file in @("README.md", "CHANGELOG.md")) {
    $sourceFile = Join-Path $sourceRoot $file
    if (Test-Path -LiteralPath $sourceFile -PathType Leaf) {
        Copy-Item -LiteralPath $sourceFile -Destination $installDir -Force
    }
}

$publicDocs = @(
    "CARTOGRAPHIE_MIDI_SYSEX.md",
    "CONFIGURATION_EC4.md",
    "GUIDE_INSTALLATION_UTILISATION.md",
    "RAPPORT_STABILISATION_UI_UPDATER_V0.5.0.md",
    "SOURCES.md"
)
$targetDocs = Join-Path $installDir "docs"
New-Item -ItemType Directory -Path $targetDocs -Force | Out-Null
$legacyDocNames = @(
    "NOTE_SECURITE_LICENCE.md",
    "RAPPORT_FAISABILITE.md",
    "RAPPORT_TESTS.md",
    "SAUVEGARDE_RESTAURATION_DESINSTALLATION.md"
)
foreach ($legacyDocName in $legacyDocNames) {
    $legacyDocPath = Join-Path $targetDocs $legacyDocName
    if (Test-Path -LiteralPath $legacyDocPath -PathType Leaf) {
        Remove-Item -LiteralPath $legacyDocPath -Force
    }
}
foreach ($legacyNestedPath in @(
    (Join-Path $targetDocs "docs"),
    (Join-Path $targetDocs "en\en")
)) {
    if (Test-Path -LiteralPath $legacyNestedPath -PathType Container) {
        Remove-Item -LiteralPath $legacyNestedPath -Recurse -Force
    }
}
foreach ($document in $publicDocs) {
    $sourceDocument = Join-Path $sourceRoot "docs\$document"
    if (Test-Path -LiteralPath $sourceDocument -PathType Leaf) {
        Copy-Item -LiteralPath $sourceDocument -Destination $targetDocs -Force
    }
}
$sourceEnglishDocs = Join-Path $sourceRoot "docs\en"
if (Test-Path -LiteralPath $sourceEnglishDocs -PathType Container) {
    $targetEnglishDocs = Join-Path $targetDocs "en"
    New-Item -ItemType Directory -Path $targetEnglishDocs -Force | Out-Null
    Get-ChildItem -LiteralPath $sourceEnglishDocs -File | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $targetEnglishDocs -Force
    }
}

$sourceProfiles = Join-Path $sourceRoot "profiles"
$targetProfiles = Join-Path $installDir "profiles"
if (Test-Path -LiteralPath $sourceProfiles -PathType Container) {
    $legacyNestedProfiles = Join-Path $targetProfiles "profiles"
    if (Test-Path -LiteralPath $legacyNestedProfiles -PathType Container) {
        Remove-Item -LiteralPath $legacyNestedProfiles -Recurse -Force
    }
    New-Item -ItemType Directory -Path $targetProfiles -Force | Out-Null
    Get-ChildItem -LiteralPath $sourceProfiles -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $targetProfiles -Recurse -Force
    }
}

if ($ControllerFile) {
    $resolvedCtrl2 = Resolve-Path -LiteralPath $ControllerFile -ErrorAction SilentlyContinue
    if (-not $resolvedCtrl2) {
        throw "Fichier Ec4.ctrl2 introuvable: $ControllerFile"
    }
    Copy-Item -LiteralPath $resolvedCtrl2.Path -Destination $installDir -Force
}
else {
    $sourceCtrl2 = Join-Path $sourceRoot "Ec4.ctrl2"
    if (Test-Path -LiteralPath $sourceCtrl2) {
        Copy-Item -LiteralPath $sourceCtrl2 -Destination $installDir -Force
    }
}

$shortcutCount = 0
if ($CreateDesktopShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $desktopShortcut = Join-Path $desktop "EC4 LiveProfessor Bridge.lnk"
    New-Shortcut -TargetPath $targetExe -ShortcutPath $desktopShortcut -Name "EC4 LiveProfessor Bridge"
    $shortcutCount++
}

if ($CreateStartMenuShortcut) {
    $menuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\EC4 LiveProfessor Bridge"
    $startShortcut = Join-Path $menuDir "EC4 LiveProfessor Bridge.lnk"
    New-Shortcut -TargetPath $targetExe -ShortcutPath $startShortcut -Name "EC4 LiveProfessor Bridge"
    $shortcutCount++
}

Write-Info "Installation terminée : $shortcutCount raccourci(s) crée(s)."
Write-Info "Vous pouvez lancer : $targetExe"
