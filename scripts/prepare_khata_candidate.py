"""Freeze allowlisted local source without committing, publishing or copying secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {"accounts", "apps", "django_project", "helpers", "pages", "templates",
               "static", "locale", "scripts", "docs", ".github"}
FILES = {"Dockerfile", ".dockerignore", ".gitignore", "requirements.txt", "requirements.lock",
         "manage.py", "AGENTS.md", "README.md"}
SUFFIXES = {".py", ".html", ".css", ".js", ".cjs", ".json", ".jsonl", ".md", ".yml", ".yaml",
            ".txt", ".lock", ".po", ".mo", ".svg", ".png", ".jpg", ".jpeg", ".gif",
            ".ico", ".webp", ".woff", ".woff2", ".ttf", ".otf", ".ps1", ".sh"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def selected_paths():
    names = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")
    for name in sorted(set(filter(None, names))):
        path = ROOT / name
        parts = Path(name).parts
        if name not in FILES and (parts[0] not in DIRECTORIES or path.suffix.lower() not in SUFFIXES):
            continue
        if any(p.startswith(".env") or p == "__pycache__" for p in parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Review symlink before packaging: {name}")
        if path.is_file():
            yield name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New local evidence directory")
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    if not destination.is_relative_to(ROOT / ".tmp"):
        parser.error("Evidence must stay inside the repository .tmp directory.")
    destination.mkdir(parents=True, exist_ok=False)
    records = []
    with ZipFile(destination / "source.zip", "x", ZIP_DEFLATED) as archive:
        for name in selected_paths():
            content = (ROOT / name).read_bytes()
            records.append(dict(path=name, bytes=len(content), sha256=hashlib.sha256(content).hexdigest()))
            info = ZipInfo(name, date_time=(2026, 10, 2, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    source_hash = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = dict(format="rokkad-local-source/1", candidate="khata-local-20261002-" + source_hash[:12],
        source_sha256=source_hash, archive_sha256=hashlib.sha256((destination / "source.zip").read_bytes()).hexdigest(),
        baseline_commit=git("rev-parse", "HEAD").decode().strip(),
        baseline_branch=git("branch", "--show-current").decode().strip(),
        committed_candidate=False, image_verified=False, remote_ci_verified=False, files=records)
    # Read back every member; reject any source edit during capture.
    with ZipFile(destination / "source.zip") as archive:
        for row in records:
            expected = row["sha256"]
            if hashlib.sha256(archive.read(row["path"])).hexdigest() != expected:
                raise ValueError("Archive integrity differs from the captured source.")
            if hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() != expected:
                raise ValueError("Source changed during capture; prepare a new candidate.")
    if set(selected_paths()) != {row["path"] for row in records}:
        raise ValueError("Source inventory changed during capture; prepare a new candidate.")
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=2))
    print(f"Verified {len(records)} source files; no Git mutation or deployment.")


if __name__ == "__main__":
    main()
