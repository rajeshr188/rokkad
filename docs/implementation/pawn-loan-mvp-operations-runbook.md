---
status: active
owner: loans
updated: 2026-08-04
tags: [loans, pawn-loan, operations, runbook]
related: [../plans/loans-rewrite-roadmap.md, ../constitution.md, ../adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md]
---

# PawnLoan MVP Operations Runbook

This runbook covers deployment, diagnosis, recovery, rollback, reconciliation,
and support for the side-by-side `loans.PawnLoan` MVP. It does not authorize
production cutover. E6.3 provides the reversible workspace gate; enabling it
still requires an approved E6.4 pilot and the checks in this runbook.

## Non-negotiable boundaries

- Loans records are serviced only by Loans; Girvi records are serviced only by
  Girvi. Never dual-write or move record ownership during support.
- Loans records source intent; DEA alone creates vouchers and journal entries.
- Never edit posted vouchers/journals, immutable accounting events, approval
  snapshots, accruals, releases, release items, or custody history.
- Corrections use administrator-only, reason-required, newest-first reversals.
- A committed regulatory number is never reset, recycled, or reassigned.

## Pre-deployment

1. Back up the database using the normal environment procedure.
2. Confirm the target commit and review migrations:

   ```powershell
   .\.venv314\Scripts\python.exe manage.py showmigrations loans
   .\.venv314\Scripts\python.exe manage.py makemigrations loans --check --dry-run
   ```

3. Apply tenant-aware migrations. Do not substitute plain `migrate`:

   ```powershell
   .\.venv314\Scripts\python.exe manage.py migrate_schemas
   ```

4. Run Django checks and the E5.5 suite before any pilot enablement:

   ```powershell
   .\.venv314\Scripts\python.exe manage.py check
   .\.venv314\Scripts\python.exe manage.py test apps.tenant_apps.loans.tests --keepdb
   ```

5. As an Owner/Admin, open `/loans/setup/operations/`. Resolve all sequence and
   accounting blockers and then open `/loans/internal/reports/` to confirm no
   unexplained reconciliation issue remains.

## Enablement

The workspace switch is `/loans/setup/cutover/` and is restricted to
Owner/Admin. It writes audited central preference `loan__new_module_enabled`.
Keep it disabled until the operations console, Loans reconciliation, E6.2
coexistence comparison, migration check, backup, rollback plan, and pilot
approval are green.

Enable one approved workspace at a time. Enabling changes new-loan navigation
and blocks Girvi origination, including direct GET/POST/HTMX entrypoints. It does
not move existing Girvi records; staff continue servicing those through
**Legacy Girvi**. Verify Party handoff from a customer link, create one Loans
draft, and complete the approved pilot workflow before wider enablement.

Run the E6.4 fail-closed gate before changing the feature flag:

```powershell
.\.venv314\Scripts\python.exe manage.py tenant_command check_pawn_loan_cutover_readiness --schema=TENANT_SCHEMA --as-of=2026-08-04 --fail-on-blocker
```

The command checks migrations, numbering, failed/stale outbox work, accounting
setup, Loans-to-DEA reconciliation, and Girvi/Loans comparison. It remains
NO-GO until backup, rollback, support, monitoring, permissions, and a real pilot
workflow have each been performed and explicitly acknowledged with the matching
`--ack-...` option. Retain `--format=json` output as release evidence.

## Failed outbox delivery

1. Open the Operations Console and the linked loan.
2. Read the durable `last_error`; do not infer success from the business action.
3. In reconciliation, verify source-event and outbox payload/fingerprint/key
   agreement and check whether a DEA voucher or journal already exists.
4. Resolve the displayed prerequisite: open accounting period, funding cash,
   principal/borrower control, Party receivable mapping, interest income,
   interest receivable, or fee income.
5. Use **Queue retry** only for a `FAILED` event. The service resets it to
   `PENDING` and delivery remains idempotent.
6. Confirm `POSTED`, DEA voucher/journal references, balanced lines, correct
   source link, and matching source/voucher economic total.

Never retry by creating a manual voucher. If reconciliation shows DEA evidence
but the outbox is failed or incomplete, stop and escalate for code/data review.

## Stale processing event

The console treats a `PROCESSING` claim older than 15 minutes as stale.

1. Confirm worker/process health and whether the original process is still live.
2. Inspect reconciliation for a posted voucher and journal.
3. Do not change the status manually and do not use failed-event retry.
4. If DEA evidence exists, escalate to reconcile the durable receipt safely.
5. If no DEA evidence exists, recover through a tested lease-recovery mechanism;
   E5.4 intentionally does not invent one through the UI.

## License and sequence blocker

- An expired or inactive license remains permanently linked to old loans but
  cannot issue a new loan.
- An inactive series/sequence cannot allocate.
- Both `PAWN_LOAN` and `PAWN_LOAN_RELEASE` sequences must exist.
- If `next_number > maximum_number`, create/select a new series. Never lower
  `next_number` or raise the maximum to disguise an exhausted regulatory range.

## Accounting setup blocker

Use the action link shown beside each blocker. For
`BORROWER_RECEIVABLE_REQUIRED`, an Owner/Admin can use **Set up borrower
accounting** to atomically create or reuse the Party compatibility Customer,
DEA account, and active `BORROWER / BORROWER_LOAN_RECEIVABLE` mapping. This is
setup only and creates no voucher or journal. Re-run the Operations Console
after setup. An approved/active loan is ready only when its current-date DEA
prerequisites pass; accrual-policy loans also require interest receivable setup.

## Reversal or custody blocker

1. Open recent reversals, the loan audit trail, and reconciliation.
2. Identify the newest unreversed event. Reverse later dependencies first.
3. Require an Owner/Admin and a concrete reason.
4. For release reversal, confirm physical custody still matches the original
   customer handoff before compensation.
5. If physical and recorded custody disagree, stop. Do not edit custody state or
   fabricate history; investigate and record an approved correction workflow.

## Reconciliation checklist

The report must have no unexplained:

- missing disbursal event or outbox;
- failed/pending accounting delivery;
- source/outbox payload drift;
- missing or mismatched DEA voucher/journal/source link;
- unbalanced or non-final DEA voucher;
- duplicate source intent or duplicate DEA documents;
- source-event versus voucher-total mismatch;
- impossible custody or closed-loan inconsistency.

Document any deliberately accepted warning with workspace, loan, source event,
owner, reason, and planned resolution. An unexplained error blocks enablement.

## Coexistence comparison gate

Run E6.2 for the target tenant after reconciliation and before pilot changes:

```powershell
.\.venv314\Scripts\python.exe manage.py tenant_command compare_loan_coexistence --schema=TENANT_SCHEMA --as-of=2026-08-04 --fail-on-mismatch
```

Use `--format=json` when a deployment job needs machine-readable evidence. The
command is read-only. It compares Girvi and Loans source projections against the
unified portfolio contract and categorizes count, lifecycle, money, custody,
release, and DEA-visibility mismatches. Do not "fix" a mismatch by moving record
ownership, editing immutable evidence, or creating a second operational copy.
Investigate the named source key in its owning app and rerun the command.

## Rollback

Application rollback must preserve data and record ownership:

1. Open `/loans/setup/cutover/` and disable **Create new pawn loans in Loans**.
   Confirm the canonical Loans entry returns to Girvi.
2. Redeploy the last schema-compatible application version.
3. Do not reverse business events merely to roll back code.
4. Do not delete Loans rows, reuse numbers, or move Loans records into Girvi.
5. Continue servicing every already-created Loans record in Loans.
6. Re-run Operations Console and reconciliation after redeployment.

Database migration reversal is allowed only when the migration is explicitly
proven reversible, no retained Loans data depends on it, and backup/restore has
been rehearsed. Prefer forward fixes.

## Support evidence to capture

- workspace ID/schema and application commit;
- loan number and `PawnLoan` ID;
- event/outbox IDs, status, attempt count, error, fingerprint, and timestamps;
- DEA voucher/journal IDs and reconciliation categories;
- current lifecycle/balance/custody state;
- license/series/sequence readiness;
- recent audit and reversal entries;
- exact operator action and time.

Do not include customer KYC documents or unnecessary personal data in support
tickets.
