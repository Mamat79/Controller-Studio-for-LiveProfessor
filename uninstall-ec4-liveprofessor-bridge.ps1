param(
    [string]$InstallPath = "$env:LOCALAPPDATA\Programs\EC4LiveProfessorBridge"
)

$ErrorActionPreference = "Stop"

function Remove-ShortcutIfExists([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
}

$installDir = Join-Path $InstallPath "EC4LiveProfessorBridge"
$desktop = [Environment]::GetFolderPath("Desktop")
$menuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\EC4 LiveProfessor Bridge"

if (Test-Path -LiteralPath $installDir) {
    Remove-Item -LiteralPath $installDir -Recurse -Force
}

Remove-ShortcutIfExists (Join-Path $desktop "EC4 LiveProfessor Bridge.lnk")
if (Test-Path -LiteralPath $menuDir) {
    Remove-Item -LiteralPath $menuDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "EC4 LiveProfessor Bridge a été retiré."
