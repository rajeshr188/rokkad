"""Check local links in curated current documentation, without network or Django."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "docs/README.md", "docs/AGENT_MEMORY.md", "docs/STATUS.md", "docs/ROADMAP.md",
    "docs/plans/active.md", "docs/plans/project-hardening.md", "docs/plans/future-work.md",
    "docs/implementation/dependency-policy.md", "docs/implementation/testing-and-migrations.md",
    "docs/domain/party.md", "docs/domain/notifications.md", "docs/archive/context/README.md",
)


def anchors(path):
    used, result = {}, set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", path.read_text(encoding="utf-8"), re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = used.get(slug, 0)
        used[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def main():
    errors, count = [], 0
    for name in SOURCES:
        source = ROOT / name
        text = source.read_text(encoding="utf-8")
        # Current guides use inline Markdown links; skip fenced examples.
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        for raw in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", text):
            link = urlsplit(raw.strip("<>"))
            if link.scheme or link.netloc:
                continue
            target = (source.parent / unquote(link.path)).resolve() if link.path else source
            count += 1
            if not target.exists():
                errors.append(f"{name}: missing target {raw}")
            elif link.fragment and target.suffix == ".md" and unquote(link.fragment) not in anchors(target):
                errors.append(f"{name}: missing heading {raw}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Checked {count} local links in {len(SOURCES)} curated documentation files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
