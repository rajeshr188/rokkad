---
status: local-technical-verification-complete-production-pending
owner: project
updated: 2026-10-05
tags: [implementation, loans, archive, acceptance, rollout]
related: [../plans/unified-loan-domain-correction.md, ../adr/2026-10-05-unified-loan-browsing-with-retained-evidence.md]
---

# Unified browsing and LD-08 technical preparation

## Delivered behavior

Loans lists ordinary loans and retained historical closed claims together, with
All records / Ordinary loans / Historical records filters. Search, CLOSED status,
original-date ranges, SQL pagination and private HTMX fragments work across the
combined directory. Historical cards link to existing retained details, do not
invent current balances, and clearly disclose their source status. Original
principal is shown only when known, explicitly as a source claim.

Repeated snapshots of one exact source identity produce one latest card. All
snapshots remain in Historical evidence. After financial admission, the ordinary
loan replaces the archive card. Source namespaces and legacy schema scopes keep
reused IDs distinct. Invalid scope cannot hide evidence through an unscoped match.
Party/licence/series selections require local mapping; the page explains how to
clear them and find an unadmitted source record by number/name. Unknown original
dates do not match either date bound.

The heading has one prominent New loan action; the series standing entry purpose
continues to select its default. Current lending setup warnings cannot hide entry
of completed transactions. The completed-loan shortcut and historical snapshots
are secondary tools. Payout guidance now points to general Record completed
payout. The imported-opening panel describes supported auction eligibility, not
a blanket prohibition. Entered-through dates are no longer labelled as proof of
transaction completeness. Closure portability guidance and the loan-journey image
reflect delivered capabilities. Servicing, approval and posting rules are unchanged.

## Why closed archives are not automatically converted

The existing private September 21 source reports were re-read without changing
them. Their source archive SHA-256 is
`f50e992a5813571e5d64316534cf073c08a96059780420be47bf7211eab163a6`.
They are an earlier snapshot, not observed live production counts or current
acceptance status.

| Source | Closed candidates | Unknown original principal | Unknown reported balance | Unknown normalized payments |
|---|---:|---:|---:|---:|
| JCL | 26,474 | 26,474 | 26,474 | 15,429 |
| JSK | 3,811 | 3,811 | 3,811 | 724 |
| Lakshmi | 8,658 | 8,658 | 8,658 | 3 |
| Total | 38,943 | 38,943 | 38,943 | 16,156 |

Raw retained source fields may supply further evidence, but these normalized
documents alone do not establish a complete financial history. JCL also has
10,624 unknown collateral records; JSK has six. Date-order findings affect 15 JCL
and four JSK records. Release-row existence is a closure claim; mutable stored
loan amounts are not verified original principal. No financial admission is
performed. A separate reviewed batch reconstruction project can classify complete
cases, reconcile terms/receipts/item splits/custody, and reuse existing admission
services for an approved batch. Format-valid evidence is not that approval.

## Generated Lakshmi acceptance example

The owner requested a generated example. These are fictional facts, not a real
Lakshmi account or staff attestation. The test uses the ordinary New loan HTTP
route with standing PAPER purpose, FlexiblePartial product, 12 months, one month
advance, ₹10 document charge and saved policy rounding. No original digital price
or approval is supplied.

Loan date: **5 April 2026**. Gold chain: ₹10,000 at 2% monthly. Silver anklets:
₹5,000 at 1.5%. Original monthly interest is ₹275; proceeds after advance and
document charge are ₹14,715. Item principal is entered with each item.

| Actual date | Recorded fact | Interest | Principal and staff split | Remaining principal |
|---|---|---:|---|---:|
| 5 April | ₹15,000 loan; ₹275 upfront interest; ₹10 charge | ₹275 upfront | Gold ₹10,000; silver ₹5,000 | ₹15,000 |
| 20 April | ₹1,275 receipt | ₹0, first month covered | Gold ₹1,000; silver ₹275 | ₹13,725 |
| 6 May | Next charge begins | ₹250.88 | Bases: gold ₹9,000; silver ₹4,725 | ₹13,725 |
| 10 May | ₹2,250.88 receipt | ₹250.88 | Gold ₹1,500; silver ₹500 | ₹11,725 |
| 6 June | Next charge begins | ₹213.38 | Bases: gold ₹7,500; silver ₹4,225 | ₹11,725 |
| 8 June | ₹11,938.38 final cash settlement and confirmed return | ₹213.38 | ₹11,725 settled | ₹0 |

The paise policy rounds each item/period HALF_UP at 0.01. With a saved whole-rupee
policy, the May charge is ₹251 and June charge ₹213; the corresponding receipt
and settlement are ₹2,251 and ₹11,938. Through 5 May the next charge is absent;
through 5 June the June charge is absent. Neither entry purpose nor today's setup
changes the captured contract.

The full-history example becomes an ordinary CLOSED loan with both items
WITH_CUSTOMER and zero debt. A separate active variant stops after the May receipt
and verifies the June boundary. With no current quotes its collateral value is
unknown. Fresh fictional gold/silver prices produce eligible value ₹32,400 and a
current LTV/risk assessment without changing the original ₹15,000 agreement.

## Verification and staging evidence

The affected regression passes **106 tests in 68.314s**: existing directory and
permission/localization behavior, archive admission, shared multi-item entry,
paper standing terms, current origination-rate checks, generated HTTP examples
and guide access. The final changed-boundary follow-up passes **14 tests in 7.756s**, including
unknown dates, explicit Workspace scope, older unscoped import compatibility and
current monitoring on the generated example. All four existing
directory JavaScript tests pass. The regenerated journey diagram was visually
checked. Earlier LD-07's 645-test financial/portability regression remains earlier
delivery evidence, not a fresh whole-repository pass.

A wider initial UI run exposed the pre-existing
`test_active_detail_exposes_complete_staff_lifecycle_and_repayment_command`
failure: it forcibly marks an unoriginated draft ACTIVE and expects renewal.
Unchanged LD-07 source reproduces it. It is outside the selected affected suite;
no origin guard is weakened. A separate stale guide assertion was aligned with
the already delivered Edit this draft wording.

Local rehearsal source: `joint_loans_20261003`, a fictional acceptance database,
not JCL/JSK/Lakshmi production. A custom PostgreSQL backup was restored into the
fresh `rokkad_ld08_stage_20261005`; all **202 public-table content fingerprints**
matched before migration. All **nine private media files** match after restore.
Original rehearsal data was not migrated or converted.

A clean image was built from LD-07 checkpoint `3c7666bb` plus an explicit scoped
allowlist, excluding unrelated dirty billing/platform/storage work. Startup exposed
a real packaging omission: the portability row contract under `docs/contracts/`
was excluded. `.dockerignore` now includes those runtime contract resources.
The corrected candidate passes runtime startup and model/migration consistency.
The cloned database applied only its pending `data_portability.0018`, `.0019` and
`loans.0058`, `.0059`, `.0060` through owner-only migration settings. The clone
already had Loans 0056/0057; this is not evidence of production's migration level.

The staged runtime uses `joint_pilot_runtime`; owner credentials are supplied only
to the migration process. Local container settings intentionally use debug,
HTTP cookies and captured mail; their deployment warnings are not production
TLS/email acceptance. No production service, Workspace record or schema changes.

Private evidence is under `.tmp/ld08/`: source-cohorts.json, focused-tests-final.txt,
baseline-ui-test.txt, database.dump, private-media.tar, restored-media.tar,
migration.log, image build logs, rehearsal.json and reader-compatible-rollback.zip.
This is preliminary local staging evidence, not a production release artifact.
The rollback archive retains LD-07 financial readers; it does not reverse schema
guards or discard legitimate transactions.

## Remaining production steps

1. Run a current read-only inventory on the named production target under its
   restricted role, including interest-contract cohorts, archive identity links
   and old-contract correction holds. Do not use the September counts as current.
2. Freeze the final clean committed candidate and its compatible reader artifact;
   verify actual target migration level, runtime guards and deployment settings.
3. Back up and restore the actual target database and private media, then exercise
   representative entry/collection/closure/monitoring journeys in its staging
   copy. The generated example supplies technical evidence; real operator and
   printer acceptance have not been claimed.
4. Review the concrete deployment result and approve controlled production rollout.
   Keep older profiles readable and require reviewed corrections where necessary;
   no bulk archive admission or old-contract conversion accompanies deployment.

LD-08 local technical preparation is delivered; live acceptance and rollout remain
pending. No production deployment is authorized or performed by this checkpoint.
