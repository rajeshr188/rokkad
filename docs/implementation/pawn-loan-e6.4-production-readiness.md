---
status: active
owner: loans
updated: 2026-08-04
tags: [loans, cutover, readiness, pilot, go-no-go]
related: [../plans/loans-rewrite-roadmap.md, pawn-loan-mvp-operations-runbook.md, ../constitution.md]
---

# PawnLoan E6.4 Production Readiness

## Decision

Engineering hardening is complete. Production enablement remains **NO-GO**
until the target workspace's manual acknowledgements are truthfully completed.
The command cannot produce GO from automated evidence alone.

## Fail-closed gate

Run the tenant command against the intended pilot workspace:

```powershell
.\.venv314\Scripts\python.exe manage.py tenant_command check_pawn_loan_cutover_readiness --schema=TENANT_SCHEMA --as-of=2026-08-04 --format=json --fail-on-blocker
```

The automated checks cover:

1. all Loans migrations applied in the tenant schema;
2. usable license/series loan and release numbering;
3. no failed or stale accounting outbox delivery;
4. no accounting setup blocker on approved or active PawnLoans;
5. zero Loans source-to-DEA reconciliation findings;
6. zero Girvi/Loans coexistence comparison mismatches.

GO also requires explicit flags after the responsible humans perform the work:

```powershell
--ack-backup --ack-rollback --ack-support --ack-monitoring --ack-permissions --ack-pilot-workflow
```

Never pass an acknowledgement merely to make the command green. The JSON result
is the deployment evidence and should be retained with the release record.

## Local evidence on 2026-08-04

| Workspace | Automated result | Manual result | Decision |
| --- | --- | --- | --- |
| `jcl1` | All six automated checks pass | Six acknowledgements pending | NO-GO |
| `jsk` | Numbering setup missing | Six acknowledgements pending | NO-GO |
| `test` | Numbering setup missing | Six acknowledgements pending | NO-GO |

The `jcl1` run initially reported two unbalanced-voucher findings and one
source/voucher amount mismatch for `PL-00001`. Investigation proved the DEA
journals were balanced: the read-only reconciliation inspector was adding the
one-sided Party account attribution line to the already-balanced GL lines. The
inspector now follows DEA materialization semantics by using the balanced
ledger-only lines for financial totals while retaining account lines as
subledger evidence. The same unchanged tenant data then passed Loans
reconciliation and coexistence comparison with zero findings.

## `jcl1` technical pilot on 2026-08-04

A pre-pilot custom-format PostgreSQL backup was written to the ignored local
artifact `backup/pre_jcl1_loans_pilot_20260804.dump`; `pg_restore --list`
validated its archive structure. A restore into an isolated database has not
yet been performed, so the backup/restore acknowledgement remains pending.

The audited workspace feature flag was enabled and then guaranteed back off
after the pilot. The normal Loans services created Party `5` and PawnLoan `4`,
official number `PL-00004`, for `E6.4 Technical Pilot 2026-08-04`. The workflow
completed draft, approval, guided borrower accounting setup, disbursal, full
repayment, zero-settlement full release, collateral return, and closure. The
loan remains closed with zero due and closure readiness true; its consumed loan
and release numbers remain permanent evidence and must not be recycled.

Both financial events are posted, source-linked, journal-linked, and balanced
at INR 1,000 debit and credit. The operational release event is posted without
fabricating DEA financial records. The loan ticket, repayment receipt, and
release memo all rendered valid non-empty PDFs. Post-pilot Loans reconciliation
and Girvi/Loans comparison returned zero findings/mismatches. The audited
cutover values are `True` followed by `False`, and the flag is currently off.

## Manual sign-off register

| Check | Current evidence | Sign-off |
| --- | --- | --- |
| Backup/restore | Pre-pilot backup created and archive listed successfully; isolated restore still pending | Pending |
| Rollback | `jcl1` audited enable/disable rehearsal completed; `PL-00004` retained and remains Loans-owned | Engineering complete |
| Support | Runbook and required evidence list exist; named pilot support owner pending | Pending |
| Monitoring | Operations console and gate cover failed/stale outbox and reconciliation; alert ownership pending | Pending |
| Permissions | Automated Owner/Admin/member boundaries pass; target staff review pending | Pending |
| Pilot workflow | `jcl1` technical full lifecycle completed; real staff/operator acceptance pending | Pending |

E6.5 must not enable a production workspace until this register is completed for
that workspace and the command returns GO with `--fail-on-blocker`.

The final engineering regression gate passed 153 tenant-aware Loans tests with
real DEA fixtures on 2026-08-04.
