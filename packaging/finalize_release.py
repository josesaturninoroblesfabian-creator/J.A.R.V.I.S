"""Stage public notices and a package inventory. Never copy application user data."""

import importlib.metadata as metadata
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist/Jarvis"
destination = BUNDLE / "_internal/licenses/paquetes"
destination.mkdir(parents=True, exist_ok=True)
inventory = []
for dist in metadata.distributions():
    name = dist.metadata["Name"]
    inventory.append({"name": name, "version": dist.version})
    for file in dist.files or []:
        if ".dist-info" not in str(file) or not any(
                term in str(file).lower() for term in ["license", "copying", "notice"]):
            continue
        source = Path(dist.locate_file(file))
        if source.is_file():
            target = destination / name / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
(BUNDLE / "_internal/licenses/packages.json").write_text(
    json.dumps(sorted(inventory, key=lambda row: row["name"].lower()), indent=2), encoding="utf-8")
for path in BUNDLE.rglob("direct_url.json"):
    if ".dist-info" in str(path):
        path.unlink()
# Distribution inputs are whitelisted in Jarvis.spec. Reject personal artifact types.
for path in BUNDLE.rglob("*"):
    if path.is_file() and (path.suffix.lower() in {".dpapi", ".sqlite3", ".db", ".ini", ".log"}
                           or path.name == "profiles.toml"):
        raise RuntimeError(f"Unexpected personal file in bundle: {path.name}")
print("Public package staged; no credentials, history or private preferences.")
