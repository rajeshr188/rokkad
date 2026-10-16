---
status: completed
owner: project
updated: 2026-10-17
tags: [repository, retention, recovery, cleanup]
---

# FW-024 individual artifact and branch retention review

The owner requested committing/pushing the completed cleanup, then proceeding with
individually reviewed artifact removal and branch pruning. The first cleanup is
committed and pushed as `d4a5d5ed6e805f356656d6b4ab4665b14d2af2b7` on
`work/loan-servicing-contract-ld01`. See the
[initial implementation](repository-hygiene-20261017.md). This follow-up changes
local storage and local Git names, with no production/schema/business behavior
change. Remote defaults, protection and remote branches stay unchanged.
The [summary manifest](repository-retention-20261017.manifest.json) records exact
branch tips, bundle/archive hashes, counts, results and private evidence digests.

## Recovery before pruning

A self-contained bundle preserves every original local branch and tag under
`.local-backups/repository-retention-20261017/local-refs-before-pruning.bundle`.
Bundle verification, an isolated mirror clone, full object integrity checking
and exact equality of all 17 original branch tips pass. The disposable mirror is
removed after validation; the original recovery bundle remains. It holds committed
Git history, not uncommitted work or customer-data backups.

Eight inactive local branch names are fully merged into the maintained branch:
`agents/rokkar-branch-query`, `dea-core-phase-1-4`, `dea-kiss`, `loan-risk-roadmap`,
`no-tenants`, `no-tenants-no-acc`, `orgs-phase-d-workspace-mgmt`, and `tenants`.
They are deleted with ordinary `git branch -d`, preserving their exact tips in
the verified bundle. No force deletion, history rewriting or remote pruning occurs.

Keep nine branches: current integration, main, rls-mvp, the named checkpoint and
release branch, both dirty-worktree branches, and the unmerged `rls` and
`tenants_workspace` histories. Merged status alone was insufficient to retire
the dirty branches. Upstream refs were refreshed without `fetch --prune`.

Two worktrees are retired through `git worktree remove` without force:
`.tmp/linode-cutover-clean-20260921` at `da3c91ec`, and the external
`../rokkad.worktrees/agents-rokkar-branch-query` at `84653457`. Both have clean
tracked state, no unique untracked files, no skip-worktree/assume-unchanged flags,
and commits in current history and the verified bundle. The cutover tree has
487 ignored bytecode files only; the external tree has no ignored files. Exact
targets were checked before removal. Process inspection found no explicit
references to those two paths; it does not establish arbitrary relative process CWDs.
The main worktree and both dirty secondary worktrees remain registered.

## Individually reviewed local artifacts

The large metadata-only inventory is compressed from 86,178,702 to 5,338,182
bytes under `.tmp/repository-hygiene-20261017/local-retention.jsonl.gz`.
The decompressed SHA-256 matches the complete original stream before the raw
duplicate is removed. Prior records naming `.jsonl` identify its original path;
the gzip now retains every original metadata row. This is lossless compression,
not disposal of source/export evidence.

Eight dated LC-07 build directories have expanded `source/` copies alongside
their original `source.zip`. Review checks every expanded file against its ZIP
member and records complete SHA-256 manifests. Each has one changed compiled
Hindi translation (`locale/hi/LC_MESSAGES/django.mo`); no tracked current text
source refers to these expanded source paths. No original source ZIP is changed.

Before expanded removal, preserve the changed binary in an adjacent
`source-retained-overrides.zip`. Verify its bytes and the unchanged base ZIP hash,
then combine those with the member-by-member baseline comparison to establish
exact reconstruction of every source file. Adjacent `source-preservation.json`
and `source-preservation.manifest.json.gz` record recovery paths, hashes and every
original expanded file. Only inventoried, rechecked files are removed; unexpected
new files prevent directory removal. Build logs, image metadata, base ZIPs,
overrides and recovery manifests remain. All eight expanded directories are now
removed: 25,807 files / 291,231,456 logical bytes. Retained overrides and adjacent
preservation records add 1,672,579 bytes. This preserves all original source bytes
while removing redundant expanded copies. A complete independent restore of the
13be3ae9 build verifies all 3,215 files / 36,298,185 bytes against the pre-removal
manifest, then removes only the disposable restored files and empty directories.

Keep customer/source exports, prepared migration packages, media, database archives,
encrypted release images, keys, active environments, unrelated dependencies and
other mixed `.tmp`/`outputs` material. In particular, the reconciliation workbook
dependency tree is retained because it has no ordinary root package/lock setup
that establishes reproducible installation. Newer release/recovery evidence is
unaffected. This pass neither assumes age implies disposability nor seeks the
earlier 9.16 GiB estimate as a deletion target.

## Recovering a retired item

To restore a local branch, fetch its original ref from the retained bundle:

```sh
git bundle verify .local-backups/repository-retention-20261017/local-refs-before-pruning.bundle
git fetch .local-backups/repository-retention-20261017/local-refs-before-pruning.bundle refs/heads/dea-kiss:refs/heads/dea-kiss
```

The retired worktree commits remain accessible from current history. Use ordinary
`git worktree add <reviewed-path> <recorded-commit>` when a historical checkout is
needed; do not overwrite a directory containing new work.

To restore a reviewed build's original expanded source, extract its retained
`source.zip` into `source/`, then extract `source-retained-overrides.zip` into that
same directory with overwrite. Compare file hashes with the adjacent compressed
manifest. The override step preserves the compiled translation present at review.
Use a new empty destination when inspecting recovery; no automatic overwrites of
current source, media or configuration are part of cleanup.

## Verification and evidence

Detailed pre-action reviews, per-file hashes, results and recovery proofs remain
ignored under `.tmp/repository-retention-20261017/`. They contain no new remote
transfer. This record and its summary document local retention decisions rather
than claiming allocated disk recovery. All 22 archived originals and reading
copies, both dirty trees' 20/7 inventoried changes, all nine kept refs and current
application source are verified unchanged. Bundle recovery passes full Git object
integrity and all 17 tip comparisons. Metadata decompression preserves the
original inventory hash. Source base/override hashes and preservation manifests
verify for all eight builds; the independent full-source restore also passes.
Current documentation links and repository guards pass. The pushed cleanup's CI
automatically runs on the integration branch; no production deployment follows.

Final closure: exact commit `693031a7` passes all six groups in
[run 38978549791](https://github.com/rajeshr188/rokkad/actions/runs/38978549791),
including 2,695 Loans tests in 2,069.620 seconds. FW-024's selected cleanup and
retention/pruning scope is complete. Routine future retention and canonical-main
alignment remain separate maintenance rather than an unbounded cleanup obligation.
