---
status: implemented-local
owner: project
updated: 2026-10-17
tags: [repository, preservation, development, cleanup]
related: [repository-cleanup-review-20261016.md, ../plans/future-work.md, ../STATUS.md]
---

# FW-024 repository hygiene and preservation

The owner authorized the [recorded cleanup](../plans/future-work.md#fw-024-repository-hygiene-and-reproducible-development-artifacts)
on 17 October, with particular care to preserve important documents. Work began
from clean `ebf2dd6e0180e68c384cc0d0e0e0d0cbd20fc5f3` on
`work/loan-servicing-contract-ld01`. The
[machine-readable summary](repository-hygiene-20261017.manifest.json) records
counts, identities, verification and private inventory locations.
These are local source/development changes; no production deployment or schema,
business-data, loan calculation or customer-source mutation is part of this work.

## Preservation before organization

- All five original context files are retained byte-for-byte alongside browsable
  copies: Status, agent memory, active plan, root README and contributor guide.
  [Snapshot index](../archive/context/2026-10-17/INDEX.md) and
  [manifest](../archive/context/2026-10-17/snapshot-manifest.json) record original
  hashes, paths, sizes, source commit and reading-copy hashes. Reading copies
  mark archived status, rebase links, normalize whitespace and add a notice.
- Eleven obsolete DEA, pre-rewrite comparison and legacy-notification documents
  move to the corresponding archive folders. Exact `.source.txt` originals are
  retained, not just recoverable through Git. The
  [move manifest](../archive/retired-documents-20261017.json) maps every file and
  hash. The [old DEA entry point](../apps/dea/README.md) now identifies retirement.
  Current dependency/domain documentation remains authoritative.
- The original template ZIP (eight DOCX/PDF references) and all five historical
  sample PDFs move to the [reference archive](../archive/reference/README.md).
  [Checksums](../archive/reference/manifest.json) match all six original assets.
  Samples are preserved evidence, not freshly generated acceptance artifacts.
- `scripts/check_document_archives.py` verifies all 22 exact originals plus
  associated reading copies. Scoped `.gitattributes` rules prevent Git newline
  conversion from corrupting these identities across Windows/Linux checkouts.

Current Status is 65 lines instead of 14,364; memory is 145 instead of 4,595;
active work is 39 instead of 501 at capture. The complete chronology remains
searchable in the archive. Current guidance reconciles the deployed 1889/V13
release with older failed/local-only candidates and preserves separate JSK,
worker capacity, provider and source/physical acceptance limits. Ten incoming
Status anchors in cutover/hardening notes point to their historical targets.
The README's obsolete 12 October release claims and `notify` repository-map name
are corrected. Contributor/editor guidance uses Django's isolated test runner.

## Reproducible inputs and generated output

Bootstrap 5.3.8 CSS/bundle are checked-in MIT-licensed browser fixtures. Original
cache bytes matched existing source-template SHA-384 integrity pins before copy;
the [fixture manifest](../../scripts/fixtures/bootstrap-5.3.8/manifest.json)
records source URLs and SHA-256/SHA-384. All five browser scripts use the shared
verifier and require no ignored output/cache or network download.
See [browser instructions](browser-layout-verification.md).

A fresh source snapshot (HEAD plus reviewed local overlay) excludes collected
static files and old sample output, and initially has no `outputs/` directory.
All nine explicit browser methods pass there in 101.564 seconds. They cover
native/imported detail, completed payout, policies/cohort, monitoring evidence
and direct/paper counter layouts. Every browser request is intercepted.
The missing STATIC_ROOT middleware warning is expected in this source-only test;
finders supply authoritative assets. No application test assertion is weakened.

Clean collection using WhiteNoise's production-style compressed manifest backend
copies 245 source assets and generates 679 postprocessed outputs. Only after
this succeeds are 661 generated `staticfiles/` files (7,143,159 bytes) removed
from Git's index. Their local bytes remain; `static/` and app static sources stay
authoritative. Root `staticfiles/` was already excluded from the Docker source
allowlist, so this is not claimed as a runtime image-size optimization.

The repository guard rejects tracked generated runtime/output roots and Python
bytecode. Ignore rules cover singular `output/`, local `backup/` and the accidental
Windows-cache tree, while duplicate output ignores are removed. The generated
PDFs are retained as archived references rather than silently excluded.

## Bounded local cleanup and retained areas

Before local mutations, the ignored action manifest records source/destination,
size, hash, references, classification and result. The metadata JSONL inventories
paths/sizes/times and conservative retention classifications under mixed local
areas; filenames do not establish provenance. Source/export contents are not
opened to classify them. Both files live under
`.tmp/repository-hygiene-20261017/`, whose location is recorded in the summary.

All 182 ignored root logs (12,406,539 bytes) have no filename references in the
searched tracked current text sources and move to `.tmp/log-archive/20261017/`.
Each destination hash matches. No log bytes are deleted. New task logs already
use a dated directory. Only 2,019 `.pyc` files beneath source-owned cache
directories are removed (22,673,364 logical bytes); paths/hashes are recorded,
resolved workspace containment is checked, and only empty cache directories
are removed. There is no recursive delete or blanket `git clean`.

Retain all customer/source media, exported/prepared packages, database archives,
encrypted application recovery, keys, active environment and local backups.
Mixed `.tmp`/`outputs` and the accidental Windows cache remain inventoried, not
mass-deleted. The last deployed, earlier deployed and failed-candidate recovery
folders remain intact. Further removal needs individual ownership/provenance,
reference and recovery-retention review; age alone is insufficient.

All five registered worktrees remain. The ticket designer has 20 untracked files
(the earlier inventory grouped these as two entries); the Girvi worktree has seven
changed entries. Their current file hashes/status are recorded privately. Even
the two clean trees can contain ignored evidence, so cleanliness alone does not
authorize retirement. All 17 local branches/checkpoints are retained. Read-only
external-tree status uses command-local exact-path `safe.directory`, not a global
trust override. No remote default, branch protection or Git history is changed.
Logical byte reductions are not measured allocated disk-space savings.

## Integration and checks

The existing work branch is the maintained integration branch for this pass.
Its pushes now match CI, alongside main/rls-mvp, PRs and manual dispatch. The
foundation job adds archive/fixture/generated-file checks and the directory and
unsaved-entry JavaScript scripts. Remote main stays historical pending an
explicit integration/default-branch transition; no force-push/pruning is implied.

Local verification includes nine fresh-input browser tests, clean static
collection, three hygiene/fixture tests, four app-boundary guard tests and all
ten directory/unsaved-entry JavaScript cases. The complete foundation JavaScript selection
also passes all 29 Node tests. All 2,620 local links across 758 documentation
files pass the expanded current-docs scan; CI uses this full selection. Import
boundaries pass for 1,256 tracked Python files. All 22 preserved originals and
reading copies verify, and Git-index whitespace checks pass. A fresh staged
checkout with no old outputs/staticfiles independently passes archive hashes,
fixture integrity, all current links and the three fixture/hygiene unit cases.
The application/domain code and migrations do not change; the 2,695-case Loans
release run remains the production baseline rather than being repeated for docs.

## Retained follow-up

Inventory-backed selective retention review and an explicit remote-default branch
transition remain separate bounded tasks. No obsolete branch/worktree is pruned
without proving its ignored/untracked content and checkpoint are preserved.
The cleanup deliberately preserves the mixed evidence that made blanket removal
unsafe. It does not claim to reclaim the earlier 9.16 GiB estimate.
