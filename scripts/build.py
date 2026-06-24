"""Builds pressure_monitor.zip for Krita plugin import."""

import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent

FILES = [
    "pressure_monitor.desktop",
    "pressure_monitor/__init__.py",
    "pressure_monitor/Manual.html",
]

out = ROOT / "pressure_monitor.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(zipfile.ZipInfo("pressure_monitor/"), "")
    for f in FILES:
        zf.write(ROOT / f, f)

print(f"Built {out}")
