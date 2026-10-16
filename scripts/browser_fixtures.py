"""Pinned, offline assets for the fictional Django/Playwright layout checks."""
import base64
import hashlib
import json
from pathlib import Path


BOOTSTRAP = Path(__file__).resolve().parent / "fixtures/bootstrap-5.3.8"


def bootstrap_assets():
    manifest = json.loads((BOOTSTRAP / "manifest.json").read_text(encoding="utf-8"))
    assets = {}
    for name, expected in manifest["assets"].items():
        path = BOOTSTRAP / name
        digest = base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()
        if digest != expected["sha384"]:
            raise ValueError(f"Browser fixture integrity mismatch: {name}")
        assets[name] = path
    return assets


if __name__ == "__main__":
    print(f"Verified {len(bootstrap_assets())} offline Bootstrap 5.3.8 fixtures.")
