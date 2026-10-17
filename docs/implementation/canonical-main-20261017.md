---
status: completed
owner: project
updated: 2026-10-17
tags: [repository, git, integration]
related: [development-workflow.md, repository-retention-20261017.md, ../STATUS.md]
---

# Bring the existing default main branch up to date

The owner selected keeping `main` as the default and advancing its historical
baseline to the maintained integration history. The original `84653457` tip is
an ancestor of verified application `b0d57294`, 713 commits behind it, with no
unique main commits. The complete original tip remains in the restore-verified
repository-retention bundle. No history rewrite or reconciliation merge is needed.

Exact application revision `b0d57294` passes all seven
[CI jobs](https://github.com/rajeshr188/rokkad/actions/runs/38986792573), including
2,717 Loans tests. The final main update adds only checked documentation and
de-identified release evidence to that application tree. Its application bytes
match the verified production candidate. Main advances by an ordinary fast-forward;
GitHub's default remains main. No protection/ruleset or merge policy is activated.

Preflight verifies the current remote tip, ancestor relationship, original-tip
recovery, worktrees, open PR targets, main-triggered workflows, protection/rulesets
and active push webhooks. No blocking protection, ruleset or active push webhook
exists. The current workflow runs CI and builds an unpublished image; a main push
does not deploy production. Production retains its separately verified immutable
application revision/image and financial-repair authority.

`work/loan-servicing-contract-ld01` remains at the verified application revision
through handover. Remote `dea-kiss`, `tenants_workspace`, `rls`, checkpoint,
release and other feature refs remain untouched. `dea-kiss` is already an ancestor;
the one unique `tenants_workspace` commit and 76 unique `rls` commits are preserved.
Existing local upstream settings and the two dirty feature worktrees remain intact.
Open PRs still target their existing base; their differences may shrink as the
base catches up. No manual PR closure, rebase or branch deletion is performed.

New work should branch from current main. Existing branches can incorporate main
through a separately reviewed merge/rebase when useful; the pointer update itself
does not modify their commits or recover an obsolete feature into today's domain.
The broader development workflow remains a proposal pending owner adoption.

## Published transition verification

The ordinary push advances remote main from `84653457` to documentation/release
revision `03a79a10`, whose application tree is identical to verified `b0d57294`.
All twelve remote heads are compared before/after: only main changes, and the
integration checkpoint stays at `b0d57294`. A fresh shallow clone selects main
and resolves HEAD to `03a79a10`; the local worktree is clean after publishing.
The remote default remains main. This follow-up records the actual published
verification; subsequent documentation commits do not change the application
release identity. Incremental Python formatting and current documentation links
are checked against the verified application baseline.
