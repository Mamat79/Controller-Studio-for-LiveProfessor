[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$installRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$expectedRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $env:LOCALAPPDATA 'Programs\Controller Studio for LiveProfessor')
)
if ($installRoot -ne $expectedRoot) {
    throw "Désinstallation refusée hors du dossier attendu : $expectedRoot"
}

$shortcutPaths = @(
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Controller Studio for LiveProfessor.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Controller Studio for LiveProfessor.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\SiLeMI-O Controller Studio for LiveProfessor.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'SiLeMI-O Controller Studio for LiveProfessor.lnk')
)
foreach ($shortcut in $shortcutPaths) {
    Remove-Item -LiteralPath $shortcut -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SiLeMIOControllerStudio' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $installRoot 'Controller-Studio-for-LiveProfessor.exe') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $installRoot 'SiLeMIO-Controller-Studio.exe') -Force -ErrorAction SilentlyContinue

$cleanup = "Start-Sleep -Milliseconds 800; Remove-Item -LiteralPath '$($installRoot.Replace("'", "''"))' -Recurse -Force"
$hostExe = (Get-Process -Id $PID).Path
Start-Process $hostExe -ArgumentList '-NoProfile', '-WindowStyle', 'Hidden', '-Command', $cleanup -WindowStyle Hidden
