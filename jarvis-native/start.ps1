param([string]$Profile = "")
$ErrorActionPreference = 'Stop'
$nativeRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $nativeRoot
$pythonPath = Join-Path $projectRoot 'OpenJarvis\.venv\Scripts\pythonw.exe'
$appPath = Join-Path $nativeRoot 'jarvis_native.py'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'No se encontró el entorno Python de OpenJarvis.'
}
if ($Profile) { $env:JARVIS_PROFILE = $Profile }
# Keep paths quoted: a future installation directory may contain spaces.
Start-Process -FilePath $pythonPath -ArgumentList ('"{0}"' -f $appPath) -WorkingDirectory $nativeRoot -WindowStyle Hidden
