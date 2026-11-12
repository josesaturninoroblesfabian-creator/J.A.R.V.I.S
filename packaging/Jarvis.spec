# Reproducible Windows x64 beta. Build with packaging/build-env.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
import os
native = root / "jarvis-native"
datas = [(str(native / "profiles.default.toml"), "."),
         (str(native / "assets/vosk-model-small-es-0.42"), "assets/vosk-model-small-es-0.42"),
         (str(root / "OpenJarvis/LICENSE"), "licenses/OpenJarvis"),
         (str(root / "packaging/THIRD_PARTY_NOTICES.md"), "licenses")]
for package in ["cv2", "certifi", "openjarvis", "vosk"]:
    datas += collect_data_files(package)
binaries = collect_dynamic_libs("vosk")
hidden = ["openjarvis_rust", "win32com.client", "pythoncom", "pywintypes"]
for package in ["openjarvis.engine", "openjarvis.agents", "openjarvis.tools", "openjarvis.skills",
                "openjarvis.security", "openjarvis.scheduler", "openjarvis.telemetry", "openjarvis.prompt"]:
    hidden += collect_submodules(package, on_error="ignore")
for name in ["openai", "vosk", "pyside6", "httpx", "ddgs"]:
    datas += copy_metadata(name)

a = Analysis([str(native / "jarvis_native.py")], pathex=[str(native), str(root / "OpenJarvis/src")],
             binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["torch", "transformers", "faster_whisper", "kokoro", "spacy", "misaki", "onnxruntime",
                       "tensorflow", "datasets", "pandas", "pyarrow", "scipy", "matplotlib", "sklearn",
                       "PyQt5", "PyQt6", "PySide2", "IPython", "pytest", "tkinter"],
             noarchive=False)
# Qt needs newer MSVC runtime exports than the Python interpreter's copy.
# Keep the redistributable versions shipped by this exact Qt wheel at root too.
import PySide6
qt_dir = Path(PySide6.__file__).parent
runtime_names = [p.name for pattern in ["VCRUNTIME140*.dll", "MSVCP140*.dll"]
                 for p in qt_dir.glob(pattern)]
a.binaries = [entry for entry in a.binaries if entry[0].upper() not in
              {name.upper() for name in runtime_names}]
a.binaries += [(name, str(qt_dir / name), "BINARY") for name in runtime_names]
# Qt on Windows uses the system ICU API. An unrelated Poppler ICU on the
# build host's PATH has version-suffixed exports and must not shadow it.
a.binaries = [entry for entry in a.binaries if entry[0].lower() not in
              {"icuuc.dll", "icuin.dll", "icudt.dll"}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Jarvis", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False,
          console=bool(os.environ.get("JARVIS_BUILD_CONSOLE")),
          version=str(root / "packaging/version.txt"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Jarvis")
