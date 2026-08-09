[CmdletBinding()]
param(
    [string]$SourceExe,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\Controller Studio for LiveProfessor')
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ([string]::IsNullOrWhiteSpace($SourceExe)) {
    $SourceExe = Join-Path $projectRoot 'dist\Controller-Studio-for-LiveProfessor.exe'
}
$SourceExe = (Resolve-Path -LiteralPath $SourceExe).Path
$programsRoot = (Join-Path $env:LOCALAPPDATA 'Programs')
$expectedRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $programsRoot 'Controller Studio for LiveProfessor')
)
if ([System.IO.Path]::GetFullPath($InstallRoot) -ne $expectedRoot) {
    throw "La destination doit être exactement $expectedRoot"
}

$null = New-Item -ItemType Directory -Force -Path $InstallRoot
$targetExe = Join-Path $InstallRoot 'Controller-Studio-for-LiveProfessor.exe'
$uninstaller = Join-Path $InstallRoot 'Uninstall-Controller-Studio-for-LiveProfessor.ps1'
Copy-Item -LiteralPath $SourceExe -Destination $targetExe -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination $uninstaller -Force

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPaths = @(
    (Join-Path $startMenu 'Controller Studio for LiveProfessor.lnk'),
    (Join-Path $desktop 'Controller Studio for LiveProfessor.lnk')
)
$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetExe
    $shortcut.WorkingDirectory = $InstallRoot
    $shortcut.Description = 'Controller Studio for LiveProfessor'
    $shortcut.IconLocation = "$targetExe,0"
    $shortcut.Save()
}

$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SiLeMIOControllerStudio'
$hostExe = (Get-Process -Id $PID).Path
$null = New-Item -Path $uninstallKey -Force
Set-ItemProperty -Path $uninstallKey -Name DisplayName -Value 'Controller Studio for LiveProfessor'
Set-ItemProperty -Path $uninstallKey -Name DisplayVersion -Value '2026.0'
Set-ItemProperty -Path $uninstallKey -Name Publisher -Value 'SiLeMI/O'
Set-ItemProperty -Path $uninstallKey -Name InstallLocation -Value $InstallRoot
Set-ItemProperty -Path $uninstallKey -Name DisplayIcon -Value $targetExe
Set-ItemProperty -Path $uninstallKey -Name UninstallString -Value "`"$hostExe`" -NoProfile -ExecutionPolicy Bypass -File `"$uninstaller`""
Set-ItemProperty -Path $uninstallKey -Name NoModify -Type DWord -Value 1
Set-ItemProperty -Path $uninstallKey -Name NoRepair -Type DWord -Value 1

Get-FileHash -Algorithm SHA256 -LiteralPath $targetExe
