[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Executable
)

$ErrorActionPreference = 'Stop'
$resolved = (Resolve-Path -LiteralPath $Executable).Path
$entries = pyi-archive_viewer -r -b $resolved
if ($LASTEXITCODE -ne 0) {
    throw "Inspection PyInstaller impossible : $resolved"
}
$productEntries = @($entries | Select-String -SimpleMatch 'silemio_control_hub')
$legacyEntries = @(
    $entries | Select-String -Pattern 'ec4lpbridge|legacy_launcher'
)
if ($productEntries.Count -eq 0) {
    throw "Aucun module SiLeMI/O trouvé dans $resolved"
}
if ($legacyEntries.Count -ne 0) {
    throw "Le produit historique a fui dans l'EXE : $($legacyEntries -join ', ')"
}
$requiredMidiEntries = @(
    'mido.backends.rtmidi',
    'rtmidi',
    'rtmidi\_rtmidi'
)
foreach ($requiredEntry in $requiredMidiEntries) {
    $matches = @($entries | Select-String -SimpleMatch $requiredEntry)
    if ($matches.Count -eq 0) {
        throw "Backend MIDI requis absent de l'EXE : $requiredEntry"
    }
}
$requiredAssetEntries = @(
    'controller-studio.ico',
    'controller-studio.png',
    'controller-studio-sidebar.png',
    'paypal-support-qr.png',
    'Controller-Studio-for-LiveProfessor-Manual-EN.pdf',
    'Controller-Studio-for-LiveProfessor-Notice-FR.pdf'
)
foreach ($requiredEntry in $requiredAssetEntries) {
    $matches = @($entries | Select-String -SimpleMatch $requiredEntry)
    if ($matches.Count -eq 0) {
        throw "Ressource visuelle requise absente de l'EXE : $requiredEntry"
    }
}
Write-Output "OK: $($productEntries.Count) entrée(s) SiLeMI/O, ressources d'aide et backend RtMidi présents, aucune entrée historique"
