---
status: active
owner: project
updated: 2026-08-07
tags: [accounting, mvp, pilot, operations]
related:
  - ../adr/2026-08-07-standalone-accounting-pilot-policy.md
  - ../plans/standalone-accounting-mvp-readiness.md
  - standalone-accounting-persistence-design.md
---

# Standalone Accounting Acceptance Pilot

## Purpose

This harness proves the synthetic MVP accounting cycle. It is not a production
bootstrap, source adapter, or cutover tool.

## Safety Boundary

The command fails unless all conditions hold:

- Django is running with `DEBUG=True`;
- the tenant already exists;
- its schema name starts with `accounting_pilot_`;
- `--confirm-synthetic` is supplied;
- `--actor-id` is the dedicated tenant owner's user ID.

It never creates or deletes a tenant. Existing non-pilot schemas cannot run it.

## Synthetic Scenario

The deterministic bootstrap creates only successor data:

- one organization and INR book;
- one open FY2026 period;
- cash, receivable, and sales ledgers;
- one synthetic customer receivable account/classification;
- ₹1,000 cash sale;
- ₹1,000 credit sale and open item;
- ₹600 customer receipt with ₹400 allocated;
- reversal of the cash sale;
- corrected replacement cash sale of ₹900.

Independent voucher numbers run from `PILOT-2026-0001` through `0005`; source
identity remains separate. Re-running returns the same evidence and does not
duplicate it.

## Run

After a disposable pilot tenant has been provisioned normally:

```powershell
python manage.py run_accounting_acceptance_pilot `
  --schema accounting_pilot_<name> `
  --actor-id <tenant-owner-user-id> `
  --confirm-synthetic
```

Expected output includes:

- five posted vouchers;
- ten conventional journal lines;
- balanced trial balance and balance sheet;
- ₹1,900 current-period result;
- ₹400 customer receivable balance;
- ₹600 open-item outstanding;
- zero classification-reconciliation difference.

## Acceptance

The owner and accountant should inspect the command output and the projected
journal/trial-balance evidence. Record their names, date, questions, and
accept/reject decision outside posted accounting rows. Sandbox acceptance does
not clear any K6 production entry gate.

## Technical Execution Record

On 2026-08-07, the normal onboarding control plane provisioned the disposable
`accounting_pilot_mvp` tenant as a fresh schema, ran all tenant migrations and
standard seeds, registered its local domain, and assigned its existing owner.
The guarded command then ran twice with identical results:

- five posted vouchers and ten journal lines;
- zero trial-balance, balance-sheet, and classification-reconciliation
  differences;
- INR 1,900 current-period result, INR 400 customer receivable balance, and
  INR 600 open-item outstanding;
- the INR 600 receipt explicitly split into INR 400 allocated and INR 200
  unapplied customer credit;
- no duplicate rows on replay; and
- no changes to any DEA table beyond the baseline data created by the standard
  tenant seed.

This clears the automated sandbox-execution check only. Owner/accountant review
and sign-off remain outstanding, and every production gate remains closed.

An internal accountant-style review accepted the paired posting, complete
reversal, corrected replacement, trial balance, statements, and customer
control-account reconciliation for the synthetic scope. Its observation that
the INR 200 unapplied receipt needed explicit presentation is now resolved by
the read-only `posted_unapplied_settlements` projection and pilot evidence.
Independent professional/user acceptance is still required before production.

## K7.6 Production-Candidate UAT Record

On 2026-08-07, a second tenant, `accounting_pilot_k7_uat`, was provisioned
through normal onboarding specifically to avoid relying on pre-K7 pilot data.
It used distinct synthetic identities for maker (`user:2`), authorizer
(`user:3`), and poster (`user:1`). All source documents entered through the
versioned sales/receipts adapter and authenticated facade.

The evidence pack and integrity command established:

- four posted source deliveries and five posted vouchers;
- cash sale version 1 for INR 900, its complete reversal, and corrected source
  version 2 for INR 850;
- one INR 1,000 credit sale/open item and one INR 600 receipt, of which INR 400
  is allocated and INR 200 remains unapplied;
- INR 1,450 cash, INR 400 receivable, INR 1,850 sales/current-period result;
- zero trial-balance and balance-sheet differences; and
- zero integrity findings or delivery errors.

The reproducible read commands are:

```powershell
python manage.py check_accounting_integrity --schema accounting_pilot_k7_uat
python manage.py accounting_evidence_pack --schema accounting_pilot_k7_uat --book PRIMARY
```

### Owner Acceptance Record — Accepted With Professional-Review Waiver

- Reviewer: project owner (user `rajesh`, durable user ID `1`)
- Role: product/workspace owner; not represented as an independent accountant
- Review date: 2026-08-07
- Evidence/book reviewed: `accounting_pilot_k7_uat / PRIMARY`
- Decision: ACCEPT
- Production scope accepted: the tested INR sales and customer-receipts MVP only
- Professional-review waiver: the owner states that an independent accountant
  is not currently available and knowingly accepts proceeding without that
  additional review
- Exceptions retained: tax/statutory compliance, bank feeds, inventory/loan
  adapters, legacy migration, and DEA replacement are not accepted or approved
- Durable approval reference: owner instruction in the project conversation on
  2026-08-07 to move ahead after reviewing the K7.6 result

This acceptance authorizes engineering to prepare and verify one narrow
sales/receipts production caller. It does not itself enable that caller, migrate
data, or replace DEA. Any wider scope requires a new evidence review and an
explicit decision.
