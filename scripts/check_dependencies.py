"""Check exact direct pins against the lock, optionally checking installed versions."""

import argparse
from importlib import metadata
from pathlib import Path
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def requirements(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            yield Requirement(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    errors = []
    for direct_file, lock_file in (
        ("requirements.txt", "requirements.lock"),
        ("requirements-dev.txt", "requirements-dev.lock"),
        ("requirements-browser.txt", "requirements-browser.lock"),
    ):
        locked = {
            canonicalize_name(req.name): req for req in requirements(ROOT / lock_file)
        }
        for req in requirements(ROOT / direct_file):
            name = canonicalize_name(req.name)
            pins = list(req.specifier)
            if len(pins) != 1 or pins[0].operator != "==" or "*" in pins[0].version:
                errors.append(f"{direct_file}: {req.name} needs one exact version")
            elif name not in locked or req.specifier != locked[name].specifier:
                errors.append(f"{direct_file}: {req.name} differs from {lock_file}")
    if args.installed:
        for req in requirements(ROOT / "requirements.lock"):
            if req.marker and not req.marker.evaluate():
                continue
            try:
                version = metadata.version(req.name)
            except metadata.PackageNotFoundError:
                errors.append(f"Missing runtime dependency: {req.name}")
                continue
            if version not in req.specifier:
                errors.append(
                    f"{req.name}: installed {version}, locked {req.specifier}"
                )
    if errors:
        print("\n".join(errors))
        return 1
    print(
        "Direct pins match locks"
        + ("; installed runtime matches" if args.installed else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
