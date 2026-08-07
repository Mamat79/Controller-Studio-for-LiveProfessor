param(
    [switch]$NoRestartExplorer
)

$script:ErrorActionPreference = "Stop"

Write-Host "Nettoyage du cache icones Windows..."

$iconCacheFolder = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Explorer"
$iconCaches = @(
    Join-Path $iconCacheFolder "iconcache*.db"
    Join-Path $iconCacheFolder "thumbcache*.db"
)

$isExplorerRunning = Get-Process -Name explorer -ErrorAction SilentlyContinue | Select-Object -First 1
if ($isExplorerRunning -and -not $NoRestartExplorer) {
    Write-Host "Arret d'Explorer (temporair) ..."
    Get-Process -Name explorer -ErrorAction SilentlyContinue | Stop-Process -Force
}

foreach ($pattern in $iconCaches) {
    Get-Item -Path $pattern -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
            Write-Host "Supprime : $($_.FullName)"
        } catch {
            Write-Warning "Impossible de supprimer : $($_.FullName)"
        }
    }
}

if (Test-Path "$env:SystemRoot\System32\ie4uinit.exe") {
    Write-Host "Rafraichissement icones shell ..."
    & "$env:SystemRoot\System32\ie4uinit.exe" -show | Out-Null
}

if ($isExplorerRunning -and -not $NoRestartExplorer) {
    Write-Host "Relance Explorer ..."
    Start-Process explorer.exe
}

Write-Host "Terminé."

