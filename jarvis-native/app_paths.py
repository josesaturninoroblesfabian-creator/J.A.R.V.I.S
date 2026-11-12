"""Writable user data is separate from read-only packaged assets."""

import os
import shutil
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
FROZEN = bool(getattr(sys, "frozen", False))


def data_dir():
    if os.environ.get("JARVIS_DATA_DIR"):
        return Path(os.environ["JARVIS_DATA_DIR"]).resolve()
    if FROZEN:
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "JarvisPersonal" / "data"
    return SOURCE_DIR / "data"


def asset_path(relative):
    return SOURCE_DIR / relative


def profile_path():
    if not FROZEN and not os.environ.get("JARVIS_DATA_DIR"):
        path = SOURCE_DIR / "profiles.toml"
    else:
        path = data_dir().parent / "profiles.toml"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(asset_path("profiles.default.toml"), path)
    return path
