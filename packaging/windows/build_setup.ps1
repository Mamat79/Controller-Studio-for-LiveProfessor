[CmdletBinding()]
param(
    [switch]$RebuildApplication
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$application = Join-Path $projectRoot 'dist\Controller-Studio-for-LiveProfessor.exe'
$setupScript = Join-Path $PSScriptRoot 'SiLeMIO-Controller-Studio.iss'
$setup = Join-Path $projectRoot 'dist\Controller-Studio-for-LiveProfessor-Setup-v2026.0.exe'
$checksum = "$setup.sha256"

if ($RebuildApplication -or -not (Test-Path -LiteralPath $application -PathType Leaf)) {
    & (Join-Path $PSScriptRoot 'build.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw "La construction de l'application a échoué avec le code $LASTEXITCODE"
    }
}

$isccCandidates = @(
    $env:ISCC_PATH,
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup 6 est introuvable. Installez-le ou définissez ISCC_PATH."
}

& $iscc $setupScript
if ($LASTEXITCODE -ne 0) {
    throw "La création de l'installateur a échoué avec le code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) {
    throw "Installateur attendu introuvable : $setup"
}

$hash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
$line = "$hash  $([System.IO.Path]::GetFileName($setup))`n"
[System.IO.File]::WriteAllText($checksum, $line, [System.Text.UTF8Encoding]::new($false))
Get-FileHash -LiteralPath $setup -Algorithm SHA256
