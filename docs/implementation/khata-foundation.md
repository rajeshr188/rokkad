---
status: active
owner: loans
updated: 2026-10-01
tags: [loans, khata, implementation, verification]
related: [../adr/2026-10-01-khata-agreement-design.md, ../architecture/khata-technical-design.md, ../plans/khata-delivery-design.md]
---

# Khata foundation and calculator

This records the first slice. The subsequent [opening checkpoint](khata-opening.md)
adds approval, custody and withdrawals; its scope supersedes the draft-only limit
below. Production and full servicing remain pending.

The owner authorized this first local implementation slice on 1 October, after
confirming independent and licence-associated series. This is backend foundation,
not a usable or activated khata product. No workspace or production migration was
performed. Existing ordinary-loan services, policies, routes and templates remain
outside this change.

## Delivered boundary

- Three direct workspace-owned models: `KhataSeries`, `KhataAccount` and
  `KhataAgreementRevision`. Migration `loans.0033_khata_foundation` adds forced RLS,
  parent ownership checks and immutable identity/evidence guards in one migration.
  The tenancy registry gates these models on that migration.
- Separate counters, optional same-workspace licences and workspace-wide account
  number uniqueness. Prefixes use uppercase letters/hyphens, width 1-12; number
  ceilings fit their width. Setup rejects existing ordinary sequence prefixes;
  allocation also rejects existing ordinary displayed-number collisions.
- First valid draft allocation locks/advances its series in the database, freezing
  licence association and number format. Preview consumes nothing. Cancellation
  cannot recycle numbers or unfreeze the association. A failed agreement save
  rolls back the draft and counter together.
- Authorized setup, idempotent draft creation, append-only agreement proposals,
  stale-revision protection and attributed cancellation. Real workspace action
  and commercial-write checks apply. Routine proposal dates must be today.
- A read-only interest illustration uses the latest saved draft proposal. Earlier
  proposals were never effective agreements and are not charged as revisions.

Only DRAFT and CANCELLED account states are admitted by the database in this
slice. There is no approval, activation, payout, collateral receipt, posted charge
or payment service, URL, navigation entry, admin registration or auto-created series.
The number-allocation trigger is the only allocator; callers must not increment
the counter again. Account identities cannot be deleted or rewritten.

Saved agreement proposals are immutable immediately. Editing means appending a
new proposal with a reason and request identity. This is simpler than mutable
draft terms followed by a separate freeze. Approval/activation evidence will be
added separately in the next workflow slice; a saved proposal is never approval.
Lender name/address are required even for an independent series.

## Calculator contract

`domain/khata.py` implements KHATA-1 with exact rational segment arithmetic and
one half-up rounding per month. Rates are always monthly percentages; monthly or
annual collection changes due dates only. The first-month floor applies once to
the opening limit/rate, including same-day settlement quotes. Later partial
periods use actual anniversary days. Annual charges sum rounded months.

The proposed technical conventions are implemented in the pure calculator:
February-29 annual dates clamp to February-28 then restore, and the last ordered
same-day revision supplies that day's terms. The original opening minimum stays
fixed. These conventions remain visible release-review items before activation.

Pure draw-position helpers maintain principal and unused entitlement separately,
floor collateral-backed eligibility to paise and enforce both LTV and entitlement.
Limit reductions require sufficient repayment; repayment does not replenish
entitlement. These functions do not prove custody, authorization or overdue
eligibility and must not be exposed as payout commands.

## Verification

The dedicated local database is `test_rokkad_khata_foundation_20261001`. It was
created/migrated through Django's owner-backed test settings. Adversarial DML uses
a NOSUPERUSER/NOBYPASSRLS test role. No development or production schema was migrated.

42 tests pass across the three khata test modules, the tenancy registry and
existing partial-month policy tests. Coverage includes:

- INR 1 crore at 1% monthly, monthly/annual collection, four-month early closure,
  opening minimum, split terms, exact rounding, short months and leap anniversaries.
- Both series modes, independent equal numbers in separate workspaces, immutable
  association/identity, number exhaustion, rollback, retry and concurrent allocation.
- Append-only proposals, stale edits, date/permission/commercial gates and pure previews.
- Restricted-role unset/foreign workspace access, forged parent links, raw evidence
  updates/deletes and attempts to activate unsupported account states.
- Existing partial-month policies, including started weeks, and ordinary counters.

Full flexible-loan workflow, document and mixed-account summary regressions remain
release gates for the later integration slice. No full khata servicing acceptance
is claimed by these foundation tests.

Migration drift, Django system checks and khata syntax/whitespace checks pass.
Documentation checks pass for 794 curated links and 25 khata-document links.

## Next slice

Add approval/activation evidence, actual collateral custody and valuation, source
operations and canonical financial selectors before enabling a first withdrawal.
Complete receipt, exchange, reduction, settlement and correction paths before a
real-workspace pilot. Documents, integrated summaries and native recovery remain
pending. Future tables require their own forced-RLS/registry/isolation coverage.
Reciprocal prefix checks when future ordinary-loan series are configured remain
an integration gate; this slice does not change ordinary setup commands.
