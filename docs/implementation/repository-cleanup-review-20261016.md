---
status: reviewed-local
owner: project
updated: 2026-10-16
tags: [repository, cleanup, documentation, development]
related: [../STATUS.md, dependency-policy.md, ../plans/active.md]
---

# Repository and local-directory cleanup review

The owner requests a review of the project directory and repository. This is a
local inventory over `f1ebb75a` plus existing uncommitted work, not a production
storage audit. No files, branches, worktrees, backups or Git history are removed.
No application behavior, dependencies or deployment settings are changed.

## Findings, in priority order

### RC-01: Preserve current work before cleanup

At inventory time the main worktree has 49 changed entries: 34 modified tracked
files and 15 untracked files. These include the approved everyday-counter work and
the independent JSK WH verification note. They are work to review and preserve,
not untracked debris. The current branch is `work/loan-servicing-contract-ld01`,
two commits ahead of its locally recorded upstream. No remote fetch is performed.

Five worktrees are registered. The detached September cutover tree and older
branch-query tree are clean; the ticket-designer tree has two untracked entries
and the older Girvi tree has seven changed entries. A merged branch does not imply
that its worktree is disposable. Preserve dirty/untracked content and release
checkpoints; retire approved clean trees with ordinary Git worktree commands.
Read-only status for the two external trees uses command-local exact-path
`safe.directory` settings; no global Git configuration is changed.

### RC-02: Generated assets remain in Git

Of 3,656 tracked files, 661 are under `staticfiles/` (6.81 MiB). Every one matches
existing ignore rules. This directory is Django's development `STATIC_ROOT`, not
the authoritative source `static/`. It contains collected originals and hashed
copies, including third-party assets. Ignoring a file does not untrack it.

Remove generated assets from the index in a bounded cleanup commit and retain
`static/`, application static sources and required dependency assets. Validate
`collectstatic` from a clean checkout/image before accepting the removal. Existing
CI already exercises collection. Production uses `/var/www/rokkad/static`, and
the Docker source allowlist already excludes root `staticfiles/`; this is mainly
repository hygiene rather than a production image-size fix. Add a small CI check
that tracked files do not reappear under generated runtime/output directories.

### RC-03: Browser acceptance depends on ignored output

Payout, monitoring-evidence, loan-architecture and the new counter-layout checks
read Bootstrap CSS/JS from `outputs/loan-detail-mockups/` and assert those files
exist. The older detail-layout helper can obtain assets, but the dependent checks
do not provision them themselves. Deleting outputs or using a fresh checkout can
therefore break these checks before any product assertion is exercised.

Provide one explicit, version-pinned fixture source or documented acquisition step
with integrity verification. Prefer ordinary shared fixture files/helpers over a
new test framework. Then prove the browser checks work without a pre-existing
`outputs` directory before treating that directory as entirely disposable.

### RC-04: Required-reading documents are oversized and mix checkpoints

Before this audit's short additions:

| Document | Lines | Logical size |
|---|---:|---:|
| `docs/STATUS.md` | 14,319 | 952 KiB |
| `docs/AGENT_MEMORY.md` | 4,561 | 331 KiB |
| `docs/plans/active.md` | 523 | 38 KiB |
| `docs/plans/future-work.md` | 1,978 | 143 KiB |

STATUS contains 454 second-level headings and substantial historical chronology.
Both MEMORY and STATUS are required agent reading; append-only history makes it
harder to find current state and reconcile implementation versus release claims.
The repository already has 222 tracked archive files and a dated context-snapshot
pattern that can be reused.

Keep STATUS focused on current source/release identities, active work, blockers and
next checks. Keep MEMORY focused on durable domain rules, owner decisions and
known operational traps. Archive dated execution history, keeping searchable
evidence and updating incoming anchors. Move completed work out of active plans
and consolidate duplicated future-work proposals without discarding acceptance
limits. Preserve ADRs, contracts and historical migrations.

A broader relative-path scan of 757 Markdown files outside `docs/archive` finds
146 unresolved references across ten files. Most are retired DEA documentation or
older audits linking removed code. These are triage candidates, not proof that
146 current user-facing links are broken. Reclassify superseded material and fix
remaining current links. The existing curated link checker has narrower scope.

### RC-05: Local artifacts need a retention inventory

Metadata-only traversal completes without errors:

| Area | Files | Logical size | Treatment |
|---|---:|---:|---|
| `.tmp/` | 244,787 | 5.46 GiB | Mixed snapshots, dependencies, rehearsals and recovery artifacts; classify first |
| `outputs/` | 4,918 | 3.70 GiB | Mixed synthetic acceptance, source exports and prepared imports; classify first |
| `media/` | 18,913 | 3.55 GiB | Business/source media; retain outside this cleanup |
| `.venv314/` | 19,677 | 429 MiB | Active developer environment; retain |
| `.git/` | 7,011 | 188 MiB | Ordinary Git storage; no history rewrite needed |
| `.local-backups/` | 6,193 | 72 MiB | Mixed recovery copies; retain until ownership/retention review |
| `.worktrees/` | 5,051 | 44 MiB | Registered tree with untracked work; preserve |

Total logical file sizes beneath this root are approximately 13.50 GiB. These are
file lengths, not measured allocated disk space; OneDrive/hard links/compression
may differ. External registered worktrees are not included in the size total.
The 9.16 GiB in `.tmp` plus `outputs` is not an immediately safe deletion estimate.
Examples include physical database tar files, encrypted application recovery,
source JSONL exports and reviewed packages. Folder names do not establish retention.

There are 182 ignored root logs (11.83 MiB). Future runs should put logs under a
single dated task directory. Source-tree bytecode and test caches are reproducible,
but avoid removing active task evidence or dependencies inside snapshots blindly.
An accidental literal `%SystemDrive%/ProgramData/Microsoft/Windows/Caches` tree
contains four ignored database cache files totaling under 1 MiB; it is a separate
candidate to remove after checking that no active helper uses it.

Use a manifest with path, size, provenance, active references and keep/archive/delete
classification. Retain current unreleased acceptance evidence. Handle source data,
recovery keys, media and backup copies through their existing retention/recovery
rules. Do not run blanket `git clean`, recursive output deletion or age-only expiry.

### RC-06: Starter and evidence organization needs a small follow-up

`CONTRIBUTING.md` still describes DjangoX as a deliberately basic project without
environment variables or Docker. README's repository map names `notify` although
the active application is `notify_v2`. VS Code enables pytest only for `accounts`
and suppresses its Git ignore-limit warning; it does not describe the supported
Django/RLS test workflow.

The root `template_pack.zip` contains eight original DOCX/PDF reference documents,
not runtime templates. Preserve provenance and decide a documented reference home.
Five tracked sample PDFs live under singular `output/pdf/`, whereas generated work
uses ignored plural `outputs/`. Review whether these are intentional fixtures or
generated previews, then standardize their home and references. Do not assume that
reference documents, frozen evidence or every binary file are expendable.

Current business-code directories match the supported domains; old Contact routes
are deliberate compatibility behavior. Historical migrations, aliases, contracts,
published snapshots and actively referenced chart assets are not cleanup targets
merely because their names are old. A full dead-code or dependency-removal audit
is not performed by this inventory.

### RC-07: Branch and CI conventions need alignment

The local origin default is `main`, whose recorded tip is dated 20 February 2024;
current development is on the October 2026 work branch. There are 17 local branches,
many already merged into current HEAD. Local remote-tracking refs may be stale;
this review does not inspect live repository settings or branch protection.

The checked-in workflow runs on pull requests, manual dispatch and pushes to
`main`/`rls-mvp`. A plain push to `work/loan-servicing-contract-ld01` does not match
that push filter. Decide the maintained integration/release branch and ensure its
push or PR flow runs required checks. Preserve release/checkpoint refs and other
sessions' work. Do not move main, delete branches, change remote defaults or force
push as an incidental cleanup action.

Git reports no garbage and nine packs (38.35 MiB) plus 148.46 MiB loose objects.
Routine automatic maintenance may pack these later; repository history rewriting
is not justified by this inventory.

## Recommended execution order

1. Review/preserve the pending application and independent documentation work.
2. Make browser fixtures reproducible, untrack collected static assets and add a
   narrow generated-file guard; verify collection/browser checks from clean inputs.
3. Compact required-reading documents using the existing archive/link conventions;
   reconcile current versus deployed checkpoints and fix starter guidance.
4. Prepare a bounded local-artifact manifest, then remove only selected reproducible
   files and retire approved clean worktrees. Keep unreleased acceptance evidence,
   business source/media and recovery artifacts until separately dispositioned.
5. Align the canonical branch/CI workflow and prune only reviewed obsolete refs.

Inventory JSON is ignored under `.tmp/repo-cleanup-review-20261016/`. Review uses
file metadata, Git state, source/reference searches and a relative-link scan. It
does not open backup/export contents, run application tests, query databases or
contact production/remotes. Documentation links and whitespace are checked for
this review's additions. Cleanup implementation remains a separate action.
