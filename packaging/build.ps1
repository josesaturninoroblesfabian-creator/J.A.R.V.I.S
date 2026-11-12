$ErrorActionPreference = 'Stop'
$jarvisRoot = Split-Path $PSScriptRoot -Parent
$jarvisPython = Join-Path $PSScriptRoot 'build-env\Scripts\python.exe'
Push-Location $jarvisRoot
try {
    & $jarvisPython -m PyInstaller --noconfirm --distpath dist --workpath packaging/build packaging/Jarvis.spec
    if ($LASTEXITCODE -ne 0) { throw 'Falló el empaquetado.' }
    & $jarvisPython packaging/finalize_release.py
    if ($LASTEXITCODE -ne 0) { throw 'Falló la comprobación de distribución.' }
    New-Item -ItemType Directory -Path (Join-Path $jarvisRoot 'release') -Force | Out-Null
    & (Join-Path $PSScriptRoot 'tools\nsis-3.13\makensis.exe') packaging/installer.nsi
    if ($LASTEXITCODE -ne 0) { throw 'Falló la creación del instalador.' }
} finally { Pop-Location }
