param(
    [string]$ControllerFile = "",
    [switch]$NoBuild,
    [string]$OutputRoot = "output\installer",
    [string]$InnoSetupCompiler = "",
    [switch]$AutoInstallInnoSetup
)

$ErrorActionPreference = "Stop"

$ScriptRoot = (Resolve-Path $PSScriptRoot).Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..")).Path

function Get-ProjectVersion {
    $pyproject = Get-Content -LiteralPath (Join-Path $ProjectRoot "pyproject.toml") -Raw
    if ($pyproject -notmatch 'version\s*=\s*"([^"]+)"') {
        throw "Impossible de lire la version depuis pyproject.toml."
    }
    return $Matches[1]
}

function Resolve-InnoSetupCompiler {
    param(
        [string]$PreferredPath,
        [bool]$AllowAutoInstall
    )

    $candidatePaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    if ($PreferredPath) {
        [void]$candidatePaths.Add($PreferredPath)
    }

    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($null -ne $command -and $command.Source) {
        [void]$candidatePaths.Add($command.Source)
    }

    $programFiles = [Environment]::GetFolderPath("ProgramFiles")
    $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
    $localAppData = [Environment]::GetFolderPath("LocalApplicationData")

    if ($programFiles) {
        [void]$candidatePaths.Add((Join-Path $programFiles "Inno Setup 6\ISCC.exe"))
    }
    if ($programFilesX86) {
        [void]$candidatePaths.Add((Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe"))
    }
    if ($localAppData) {
        [void]$candidatePaths.Add((Join-Path $localAppData "Programs\Inno Setup 6\ISCC.exe"))
    }

    foreach ($path in $candidatePaths) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            return (Resolve-Path -LiteralPath $path).Path
        }
    }

    if (-not $AllowAutoInstall) {
        return $null
    }

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        return $null
    }

    Write-Host "Inno Setup non trouvé. Tentative d'installation via winget..."
    $winget = (Get-Command winget).Source
    $args = @(
        "install",
        "--exact",
        "--id",
        "JRSoftware.InnoSetup",
        "--accept-source-agreements",
        "--accept-package-agreements",
        "--disable-interactivity",
        "--silent"
    )

    $wingetOutput = & $winget @args 2>&1
    if ($LASTEXITCODE -ne 0) {
        if ($wingetOutput) {
            Write-Verbose ($wingetOutput -join [Environment]::NewLine)
        }
        Write-Warning "L'installation automatique d'Inno Setup avec winget a échoué. Code: $LASTEXITCODE."
        if ($wingetOutput) {
            Write-Host "Sortie winget :"
            $wingetOutput | ForEach-Object { Write-Host "  $_" }
        }
        return $null
    }

    if ($wingetOutput) {
        Write-Host "Sortie winget :"
        $wingetOutput | ForEach-Object { Write-Host "  $_" }
    }
    $programFiles = [Environment]::GetFolderPath("ProgramFiles")
    $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")

    if ($programFiles) {
        [void]$candidatePaths.Add((Join-Path $programFiles "Inno Setup 6\ISCC.exe"))
    }
    if ($programFilesX86) {
        [void]$candidatePaths.Add((Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe"))
    }

    foreach ($path in $candidatePaths) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            return (Resolve-Path -LiteralPath $path).Path
        }
    }

    return $null
}

function Resolve-ControllerFile {
    param([string]$PathHint)

    if ($PathHint) {
        $candidate = Resolve-Path -LiteralPath $PathHint -ErrorAction SilentlyContinue
        if (-not $candidate) {
            throw "Le fichier de contrôleur n'a pas été trouvé : $PathHint"
        }
        return $candidate.Path
    }

    $localCandidate = Join-Path $ProjectRoot "Ec4.ctrl2"
    if (Test-Path -LiteralPath $localCandidate) {
        return (Resolve-Path -LiteralPath $localCandidate).Path
    }

    return ""
}

function Write-SetupScript {
    param(
        [string]$InstallerPath,
        [string]$Version,
        [string]$IconPath,
        [string]$OutputDir,
        [string]$AppSource
    )

    $outputFileName = "EC4-LiveProfessor-Bridge-Setup-v$Version"
    $appSourcePattern = Join-Path $AppSource "*"
    $setupContent = @"
[Setup]
AppId={{9C6F0D7D-7B0E-4E0B-8D3E-9C44B3FA0B4A}}
AppName=EC4 LiveProfessor Bridge
AppVersion=$Version
AppVerName=EC4 LiveProfessor Bridge $Version
AppPublisher=SiLeMI/O
DefaultDirName={localappdata}\Programs\EC4LiveProfessorBridge\EC4LiveProfessorBridge
DefaultGroupName=EC4 LiveProfessor Bridge
AllowNoIcons=yes
DisableProgramGroupPage=no
OutputBaseFilename=$outputFileName
OutputDir=$OutputDir
Compression=lzma
SolidCompression=yes
SetupIconFile=$IconPath
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: desktopicon; Description: "&Créer un raccourci sur le bureau"; GroupDescription: "{cm:AdditionalIcons}"
Name: startmenuicon; Description: "Créer un raccourci dans le &menu Démarrer"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "$appSourcePattern"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\\EC4 LiveProfessor Bridge"; Filename: "{app}\\EC4-LiveProfessor-Bridge.exe"; WorkingDir: "{app}"; IconFilename: "{app}\\EC4-LiveProfessor-Bridge.exe"; Tasks: desktopicon
Name: "{group}\\EC4 LiveProfessor Bridge"; Filename: "{app}\\EC4-LiveProfessor-Bridge.exe"; WorkingDir: "{app}"; IconFilename: "{app}\\EC4-LiveProfessor-Bridge.exe"; Tasks: startmenuicon
Name: "{group}\\Désinstaller EC4 LiveProfessor Bridge"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\\EC4-LiveProfessor-Bridge.exe"; Description: "Lancer EC4 LiveProfessor Bridge"; Flags: nowait postinstall skipifsilent

"@

    Set-Content -LiteralPath $InstallerPath -Value $setupContent -Encoding UTF8
    return $outputFileName
}

$version = Get-ProjectVersion
$installerVersionDir = Join-Path $ProjectRoot $OutputRoot
$stagingName = "EC4-LiveProfessor-Bridge-v$version-Setup-Staging"
$stagingPath = Join-Path $installerVersionDir $stagingName
$appSourcePath = Join-Path $stagingPath "source"
$installerOutputPath = Join-Path $installerVersionDir "windows"

if (-not (Test-Path -LiteralPath $installerVersionDir)) {
    New-Item -ItemType Directory -Path $installerVersionDir -Force | Out-Null
}

if (-not $NoBuild) {
    Write-Host "Build de l'application..."
    & (Join-Path $ProjectRoot "scripts\build.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Build échoué."
    }
}

$exePath = Join-Path $ProjectRoot "output\windows\EC4-LiveProfessor-Bridge.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "EC4-LiveProfessor-Bridge.exe introuvable : lancez le build avant de créer l'installateur."
}

$iconPath = Join-Path $ProjectRoot "src\ec4lpbridge\assets\ec4lp.ico"
if (-not (Test-Path -LiteralPath $iconPath)) {
    throw "Icone introuvable: $iconPath"
}

$resolvedCtrl2 = Resolve-ControllerFile -PathHint $ControllerFile

if (Test-Path -LiteralPath $stagingPath) {
    Remove-Item -LiteralPath $stagingPath -Recurse -Force
}
New-Item -ItemType Directory -Path $appSourcePath -Force | Out-Null

Copy-Item -LiteralPath $exePath -Destination $appSourcePath
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination $appSourcePath
Copy-Item -LiteralPath (Join-Path $ProjectRoot "config.example.json") -Destination $appSourcePath
Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs") -Destination (Join-Path $appSourcePath "docs") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "profiles") -Destination (Join-Path $appSourcePath "profiles") -Recurse -Force

if ($resolvedCtrl2) {
    Copy-Item -LiteralPath $resolvedCtrl2 -Destination (Join-Path $appSourcePath "Ec4.ctrl2") -Force
}

$issPath = Join-Path $stagingPath "EC4-LiveProfessor-Bridge-Installer.iss"
$outputFileName = Write-SetupScript -InstallerPath $issPath -Version $version -IconPath $iconPath -OutputDir $installerOutputPath -AppSource $appSourcePath

if (Test-Path -LiteralPath $installerOutputPath) {
    Remove-Item -LiteralPath $installerOutputPath -Recurse -Force
}
New-Item -ItemType Directory -Path $installerOutputPath -Force | Out-Null

$isccPath = Resolve-InnoSetupCompiler -PreferredPath $InnoSetupCompiler -AllowAutoInstall:$AutoInstallInnoSetup
if (-not $isccPath) {
    Write-Warning "Inno Setup 6 (iscc.exe) n'est pas installé ou non trouvé dans le PATH."
    Write-Host "Le script ISS a bien été généré ici : $issPath"
    Write-Host "Copiez ce projet sur une machine avec Inno Setup 6 puis lancez :"
    Write-Host "  iscc $issPath"
    Write-Host "Pour générer l'installateur, fournissez également Ec4.ctrl2 via -ControllerFile si nécessaire."
    exit 1
}

Write-Host "Compilation de l'installateur avec $isccPath..."
& $isccPath $issPath
if ($LASTEXITCODE -ne 0) {
    throw "La compilation Inno Setup a échoué."
}

$finalInstaller = Join-Path $installerOutputPath "$outputFileName.exe"
if (-not (Test-Path -LiteralPath $finalInstaller)) {
    throw "Installateur introuvable après compilation : $finalInstaller"
}

Write-Host "Installateur prêt : $finalInstaller"
