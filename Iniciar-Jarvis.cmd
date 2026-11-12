@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\JarvisPersonal\Jarvis.exe" (
    start "" "%LOCALAPPDATA%\Programs\JarvisPersonal\Jarvis.exe"
    exit /b 0
)
set "JARVIS_PYTHON=%~dp0OpenJarvis\.venv\Scripts\pythonw.exe"
if not exist "%JARVIS_PYTHON%" (
    echo No se encontro el entorno Python de OpenJarvis.
    pause
    exit /b 1
)
start "" /D "%~dp0jarvis-native" "%JARVIS_PYTHON%" "%~dp0jarvis-native\jarvis_native.py"
