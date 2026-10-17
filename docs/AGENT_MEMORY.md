---
status: active
owner: project
updated: 2026-10-17
tags: [agents, context, architecture]
---

# Agent Memory

This is durable project guidance. [Status](STATUS.md) owns current delivery and
blockers. All earlier decisions, owner clarifications and execution notes remain
in the [17 October snapshot](archive/context/2026-10-17/INDEX.md), with exact
original bytes and checksums. Read the relevant historical section before acting
on an old source/import/customer-specific instruction; a summary is not a new
financial authorization.

## Product and tenant foundation

Rokkad is shared-schema pawn-lending SaaS. Supported business apps are Party,
Loans, Rates and Notify v2. Retired DEA/accounting, Girvi, Contact, Product and
legacy Notify must not return as dependencies. Historical migrations, explicit
compatibility routes and Party contact permission aliases are intentional.

Workspace-owned rows require direct non-null ownership, forced PostgreSQL RLS,
registry coverage and restricted-role isolation tests. Workspace resolution,
membership, ownership, lifecycle, billing, authorization and entitlements remain
separate checks. Read [control-plane contracts](architecture/control-plane-contracts.md)
before changing them. Never infer authority from the selected Workspace alone.

Use ordinary Django and existing services/selectors/commands. Keep posting and
lifecycle mutation out of views, calculations out of templates, and cross-app
reads at existing facades/selectors. KISS never overrides evidence, tenant or
accounting safeguards. See [constitution](constitution.md), [ADRs](adr/),
[domain guides](domain/) and [dependency policy](implementation/dependency-policy.md).

## Origination, corrections and source evidence

Direct, earlier-paper and supported imported/opening loans share PawnLoan
servicing capabilities. Entry method describes source evidence; it must not
invent a separate later lifecycle. Number reservations and historical ranges
must coexist without reassigning original numbers or consuming new-loan counters.
Frozen original agreements, completed money/custody actions and source documents
remain immutable. Supported corrections append evidence/compensation, validate
predecessors and dependent history, and preserve real cash and history limits.

Use the [unified recording flow](flows/unified-loan-recording.md),
[shared correction flow](flows/correct-a-disbursed-loan.md),
[origination consolidation](implementation/loan-origination-consolidation-20261014.md)
and [financial read models](domain/pawn-loan-financial-read-models.md).
Borrower/collateral fact correction and principal/agreement correction have
different evidence/dependency gates. Never substitute a raw model update.

Retained aggregate opening-review/2 corrections preserve their original-principal,
inclusive-anniversary, first-month-paid and cumulative HALF_EVEN rules; do not
upgrade them to monthly checkpoint shapes. Their corrected portable graph requires
[servicing bundle 8](contracts/loan-servicing-bundle-v8.md), also required for
unserviced native policy-1 corrections retaining their legacy calendar and explicit
original proceeds. Later legacy servicing still requires connected reconciliation.
A pure rate proposal
cannot establish unrecorded payments or authorize production application.

Represented positions and actual source transactions are distinct evidence.
Optional paper-book assurance cannot disable otherwise supported servicing.
Required missing transaction evidence remains a blocker for the affected action;
monitoring/balances must not fabricate unavailable payout or receipt histories.
See [represented-position coverage](implementation/represented-position-coverage-20261016.md).

Portability owns versioned wire contracts independently of model metadata.
Published schemas/row definitions, source aliases, hashes, identity bindings and
immutable provenance are not generated debris. Generic model import cannot admit
Loans graphs; supported admission/restore services enforce their own gates.
Historical evidence-only archives do not imply an operational loan. Restored
closed positions must not invent opening grace or financial events. See
[portability constraints](domain/loans-portability-constraints.md).

## Monitoring and valuation

Monitoring is a derivative assessment of current debt, DPD, maturity, collateral
coverage and evidence completeness. It does not post charges, choose recovery or
send communication automatically. Saved origination valuation and current
monitoring policy are separate; preservation of a saved method is not proof of
historical business practice.

The owner's preferred new-policy default is CALCULATED_METAL_VALUE across
Workspaces; lower-of current metal and approved appraisal remains an explicit
choice. Existing loan evidence, snapshots and published portable meanings stay
unchanged. Amend the effective policy using its predecessor; do not create an
overlapping unlinked period. Omitted amendment fields retain predecessor values.
Missing/old prices, appraisals, physical custody and paper-book checks remain
independent evidence dimensions. Never turn unknown evidence into healthy coverage.
See [monitoring architecture](architecture/post-origination-loan-monitoring.md)
and [calculated default](implementation/calculated-monitoring-default-20261016.md).

Workers require explicit Workspace context, bounded transactions and preserved
refresh/recovery contracts. Scheduling/pooling/reuse optimizations require
measurement; the one-hour large-scale freshness target remains unproven. The
owner paused large local load runs until better hardware; do not resume them
without resumption. See [FW-004](plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity)
and [worker architecture](architecture/monitoring-worker-lifecycle-and-scaling.md).

## Khata and physical evidence

Khata has its own account/limit/custody and interest contract; it is not ordinary
PawnLoan assessment or a revolving repay-and-redraw facility. Preserve agreed
monthly rate units, anniversary calculations, actual principal versus limit,
formal revisions and physical handovers. Same-metal exchange and reduction-return
coverage rules differ. Refer to [Khata workflow](flows/khata-account-workflow.md)
and [confirmed requirements](plans/khata-agreements.md) before changing behavior.
Physical print, source-book and hardware acceptance are separate from unit tests.
Individual collateral identity is not established by a description/photo alone.

## Billing, notifications and private data

Billing is control-plane data. Browser actions use canonical owner/Membership or
existing platform override; verified captured-payment evidence precedes access.
Payment replay cannot renew twice or reactivate expired terms. Frozen checkout,
refund/review and recurring-cycle evidence stay immutable. Recurring provider
acceptance and live checkout gates must not be inferred from local Test Mode
checks. Use [billing flow](flows/subscription-checkout.md) and
[rollout plan](plans/subscription-monetization-rollout.md).

Notify v2 delivers authorized intent; it is not the source of loan state.
Delivery failure does not undo a completed loan action. Platform-owner WhatsApp
live provider/sender acceptance remains separate and sending remains disabled at
the last verified release. Never dispatch fictional test contacts or expose the
full local app through a callback tunnel. See [PW-05](implementation/platform-whatsapp-pilot-pw05.md).

Media/source exports can contain private customer data. Access uses existing
Workspace/object authorization; preserve private-media and backup/key custody.
Ignored outputs, snapshots, DB archives and encrypted application images are not
necessarily disposable. Do not print secrets, commit dumps or bulk-delete artifacts.
Prior transfer approvals have specific destinations/scopes and are not universal.
See [private media](implementation/private-media-access.md) and
[cleanup preservation record](implementation/repository-hygiene-20261017.md).

## Development and repository conventions

The [development workflow proposal](implementation/development-workflow.md) connects
task isolation, verification, PR integration, dependency maintenance and releases.
It remains proposed pending owner adoption; do not claim its remote checks/protection
or new merge/release policy are active merely because the guide exists.

Python 3.14 and PostgreSQL 16 development/CI baseline; use pinned direct
runtime requirements plus the uv-generated universal `requirements.lock`.
Current local requirements advance Django to 6.1.2; production stays on its verified
release until a reviewed deployment. Development tools have separate pinned
requirements/constraints and must not enter application images. Use project-local
uv/Black/Ruff, `scripts/check_dependencies.py --installed` and
`scripts/check_python_quality.py` (Ruff correctness plus changed-file Black).
Never freeze accumulated environment extras into runtime requirements. See the
[17 October dependency audit](implementation/python-dependency-audit-20261017.md).
Owner-only migrations use
`python manage.py migrate --settings django_project.settings.migration`.
Web/workers always use restricted runtime credentials. Tests use
`--settings django_project.settings.test`; adversarial DML must run restricted.
Never test against normal business databases or run competing suites on one DB.
See [testing](implementation/testing-and-migrations.md) and
[container/CI](implementation/container-and-ci.md).

Maintained integration is `work/loan-servicing-contract-ld01`; main remains a
historical remote default until an explicitly reviewed transition. CI includes
integration pushes, PRs and manual dispatch. Preserve checkpoints and dirty trees.
Local pruning uses a self-contained, restore-verified recovery bundle; keep
unmerged history and dirty worktrees. See [retention decisions](implementation/repository-retention-20261017.md).
Static source lives in `static/`/app static folders; `staticfiles/` is collected
output. Browser fixtures are versioned under `scripts/fixtures/`; old outputs are
not prerequisites. Logs belong in `.tmp/<dated-task>/`; synthetic visual output
in `outputs/<dated-task>/`. Original binary references live in
[reference archive](archive/reference/README.md). See [contributing](../CONTRIBUTING.md).
