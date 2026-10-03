---
status: active
owner: loans
updated: 2026-10-01
tags: [loans, khata, custody, approval, withdrawals, verification]
related: [khata-foundation.md, ../adr/2026-10-01-khata-agreement-design.md, ../architecture/khata-technical-design.md]
---

# Khata opening and staged withdrawals

The owner instructed proceeding after the foundation checkpoint. This second
local backend slice adds opening approval, custody evidence and withdrawals.
There are no khata URLs, navigation entries or automatic workspace setup, and
no production migration or activation. Full servicing remains a release gate.

The later [interest collection checkpoint](khata-interest-collection.md) adds
completed-month charges and actual receipts. The scope and test counts below
describe this earlier opening checkpoint.

## Implemented boundary

Migration `loans.0034_khata_opening` adds five directly workspace-owned tables:
`KhataOperation`, `KhataPolicyRevision`, `KhataCollateralItem`,
`KhataCollateralValuation` and `KhataCollateralPhoto`. All have forced RLS,
registry coverage, parent checks and database update/delete protection.
Accounts now admit APPROVED and ACTIVE in addition to DRAFT/CANCELLED. These
are projections of immutable operations. First withdrawal supplies `opened_on`;
approval alone does not create principal or start interest.

`services/khata_opening.py` provides:

- Actual collateral receipt with item facts, storage reference and handing-over
  party. Receipt alone creates no money. Each receipt currently records one item.
- Append-only JPEG/PNG photos, verified bytes/hash and private storage references.
  The file-field inventory includes khata photos; automatic deletion is disabled.
  Failed database transactions can leave uploaded bytes for the existing reviewed
  storage-reconciliation workflow, not immediate file deletion.
- Reviewed opening approval by existing loan approvers. The saved agreement
  proposal remains immutable. New proposals before first payout need new approval;
  active agreement changes require the later formal revision workflow.
- First and repeated actual withdrawals by users with `loan.disburse`. Payment
  reference, amount, approval, agreement, current policy, quote/photo evidence and
  per-item valuations are retained. Account sequence and request UUID prevent
  duplicate effects; changed requests and stale reviews fail.
- Actual return of unopened collateral with recipient/reason. Cancellation fails
  while any item remains held, and cannot cancel an active account. Active returns
  cannot use this helper; they need exchange, reduction or settlement.
- Owner-only append-only WARN/BLOCK policies, defaulting to WARN/WARN when no row
  exists. Overdue blocking applies to withdrawals; deposits remain possible.
  Exchange policy is stored for the later exchange workflow, not enforced by an
  exchange command in this slice.

## Valuation and review rules

Opening and each payout use current positive same-day INR pure-metal buying
quotes through the Rates facade/origination selectors. Gold and silver valuation
uses net weight times purity times price, rounded down to paise. There is no
manual value override in this slice. Missing, stale and future-only quotes fail.
Each completed approval/payout stores typed item and rate references plus price
evidence; a new quote never rewrites an earlier valuation.

The workspace photo requirement remains optional by default. Collateral can be
received without a photo; when mandatory, all held items need usable photo bytes
before approval/payout. First payout checks its approval date, agreement and
frozen collateral/photo/licence evidence. Changes require a fresh review and,
where opening approval is stale, a new approval. Later payouts review current
prices, coverage, policies, principal and remaining entitlement.

Commands lock workspace then account. The same workspace lock is used by Rates
and photo-policy writes. All ordinary entries use today's business date.
Associated inactive/expired/future/legacy licences block new lending; an
independent series has no licence check. Number exhaustion affects new account
creation, not further withdrawals from an already approved account.

## Financial and database guarantees

Principal is the sum of immutable withdrawal amounts; unused entitlement is the
opening limit less those amounts. Limit revisions and repayments are not admitted
yet, so the selector cannot silently ignore them. Interest uses the full opening
limit and monthly rate, with monthly/annual anniversary collection. Returned
interest values are calculated quotes, not posted interest or payment allocations.
Due means the anniversary has arrived; overdue starts the following day.

Database guards enforce operation shape, consecutive sequence, same-account
approval/terms/items, finite values and immutable source records. Deferred guards
require receipt/photo child evidence and a valuation for every held item. Payout
totals cannot exceed the agreement limit or frozen collateral LTV, including raw
DML. Lifecycle updates must match source operations. Row isolation never depends
on a licence being present.
Valuation children must match the operation's frozen item/rate/value/evidence
snapshot exactly, and completion checks its row count. Later deposits cannot
extend a completed operation's valuation evidence.

## Verification

74 tests pass across khata opening/foundation/calculation/concurrency, tenancy
registry, existing partial-month policies and storage inventory. Tests use the
dedicated local `test_rokkad_khata_foundation_20261001` database. Populated
adversarial evidence tests run as a NOSUPERUSER/NOBYPASSRLS role, including forged
parents, raw update/delete, incomplete operations and an over-LTV payout.

The suite covers separate approval/payout permissions, mandatory-photo policy,
stored photo integrity, stale quotes/reviews, repeated and concurrent payouts,
rollback, reapproval after term edits, current overdue policy and unpaid-account
return/cancellation. Original flexible partial-period policy tests still pass.
This is not full flexible-loan integration or khata-servicing acceptance.

Migration drift, Django system checks, documentation links and syntax/whitespace
checks pass. Migration 0034 was also reversed and reapplied on the dedicated
local test database after verifying it contained no khata operation/custody rows.
No development or production database was migrated.

## Remaining delivery

Interest periods/receipts and allocations, formal limit/rate revisions, same-metal
exchanges, reductions, full settlement, pending handover and compensating
corrections remain pending. Then add screens, private document issues, mixed
borrower summaries and native recovery. Do not pilot this partial servicing system.
Ordinary JCL/JSK/Lakshmi lending rules and workflows are not changed by this slice.
