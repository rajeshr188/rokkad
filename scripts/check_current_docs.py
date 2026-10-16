"""Check current documentation links without network or Django; archives are frozen."""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "CONTRIBUTING.md",
    "docs/implementation/repository-hygiene-20261017.md",
    "docs/implementation/repository-retention-20261017.md",
    "docs/implementation/repository-cleanup-review-20261016.md",
    "docs/implementation/browser-layout-verification.md",
    "docs/archive/context/2026-10-17/INDEX.md",
    "docs/archive/reference/README.md",
    "docs/apps/dea/README.md",
    "scripts/fixtures/bootstrap-5.3.8/README.md",
    "docs/adr/2026-10-16-represented-position-transaction-coverage.md",
    "docs/implementation/represented-position-coverage-20261016.md",
    "docs/adr/2026-10-16-calculated-monitoring-default.md",
    "docs/implementation/calculated-monitoring-default-20261016.md",
    "docs/adr/2026-10-15-shared-agreement-financial-corrections.md",
    "docs/contracts/loan-agreement-correction-v1.md",
    "docs/contracts/loan-servicing-bundle-v7.md",
    "docs/plans/shared-agreement-financial-corrections-20261015.md",
    "docs/implementation/shared-agreement-financial-corrections-20261015.md",
    "docs/adr/2026-10-15-shared-loan-fact-corrections.md",
    "docs/contracts/loan-servicing-bundle-v6.md",
    "docs/implementation/shared-loan-corrections-20261015.md",
    'docs/plans/loan-origination-consolidation-20261014.md',
    'docs/implementation/loan-origination-consolidation-20261014.md',
    'docs/architecture/loan-origination-review-20261014.md',
    'docs/adr/2026-10-14-origination-consolidation.md',
    'docs/contracts/loan-servicing-bundle-v5.md',
    "docs/plans/bronze-monitoring-20261014.md",
    "docs/implementation/bronze-monitoring-20261014.md",
    "docs/adr/2026-10-14-bronze-reference-price-valuation.md",
    "docs/implementation/platform-whatsapp-pilot-pw05.md",
    "docs/plans/platform-whatsapp-sender-setup-20261014.md",
    "docs/implementation/platform-whatsapp-controls-pw04.md",
    "docs/implementation/platform-whatsapp-transport-pw03.md",
    "docs/implementation/platform-whatsapp-source-intents-pw02.md",
    "docs/implementation/platform-whatsapp-enrollment-pw01.md",
    "docs/plans/platform-owner-whatsapp-phase1-20261014.md",
    "docs/adr/2026-10-14-platform-whatsapp-delivery-boundary.md",
    "docs/architecture/control-plane-contracts.md",
    "README.md", "docs/architecture/post-origination-loan-monitoring.md",
    "docs/README.md", "docs/AGENT_MEMORY.md", "docs/STATUS.md", "docs/ROADMAP.md",
    "docs/plans/active.md", "docs/plans/project-hardening.md", "docs/plans/future-work.md",
    "docs/implementation/dependency-policy.md", "docs/implementation/testing-and-migrations.md",
    "docs/domain/party.md", "docs/domain/notifications.md", "docs/archive/context/README.md",
    "docs/flows/loan-journey.md",
    "docs/implementation/new-user-journey-audit-20261014.md",
    "docs/implementation/new-user-journey-refinement-20261014.md",
    "docs/plans/new-user-journey-improvements-20261014.md",
    "docs/adr/2026-10-14-new-user-journey-handoffs.md",
    "docs/adr/2026-10-14-monitoring-choice-business-package.md",
    "docs/implementation/monitoring-portability-followup-20261014.md",
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-current", action="store_true",
                        help="Also check every Markdown file outside docs/archive.")
    args = parser.parse_args()
    sources = list(SOURCES)
    if args.all_current:
        sources.extend(("AGENTS.md",))
        sources.extend(path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "docs").rglob("*.md"))
                       if "archive" not in path.relative_to(ROOT / "docs").parts)
        sources = list(dict.fromkeys(sources))
    errors, count = [], 0
    for name in sources:
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
    print(f"Checked {count} local links in {len(sources)} documentation files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
