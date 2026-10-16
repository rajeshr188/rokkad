"""Verify exact originals and reading copies retained by FW-024."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    count = 0
    for name, key in (
        ("docs/archive/context/2026-10-17/snapshot-manifest.json", "documents"),
        ("docs/archive/retired-documents-20261017.json", "files"),
        ("docs/archive/reference/manifest.json", "files"),
    ):
        for row in json.loads((ROOT / name).read_text(encoding="utf-8"))[key]:
            path = ROOT / row.get("original", row.get("destination", ""))
            data = path.read_bytes()
            if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError(f"Original document checksum mismatch: {path.relative_to(ROOT)}")
            if "archive_sha256" in row:
                archive = ROOT / row["archive"]
                if hashlib.sha256(archive.read_bytes()).hexdigest() != row["archive_sha256"]:
                    raise ValueError(f"Archive reading copy changed: {archive.relative_to(ROOT)}")
            count += 1
    print(f"Verified {count} preserved originals and all associated reading copies.")


if __name__ == "__main__":
    main()
