---
status: completed
owner: project
updated: 2026-09-21
tags: [implementation, migration, portability, production-discovery]
related: [../architecture/production-tenants-to-rls-migration.md]
---

# Linode production discovery snapshot: 2026-09-21

## Scope and handling

This report describes a read-only discovery snapshot supplied by the owner. No
connection was made to Linode, no archive was restored, and no target Workspace
data was written. The file is PostgreSQL custom format, despite its `.sql`
extension.

| Fact | Value |
| --- | --- |
| Source database | `rokkaddbv1` |
| Server and dump version | PostgreSQL 15.7 |
| Archive checksum (SHA-256) | `f50e992a5813571e5d64316534cf073c08a96059780420be47bf7211eab163a6` |
| Requested source schemas | `jcl`, `jsk`, `lakshmipawnbroker` |
| Source model family | legacy `contact_*`, `girvi_*`, `dea_*`, plus other retired application tables |

The archive catalog contains other schemas. They are outside this migration scope.

## Confirmed Company map

| Source schema | Legacy Company ID | Legacy Company name |
| --- | ---: | --- |
| `jcl` | 2 | `jcl` |
| `jsk` | 3 | `jsk` |
| `lakshmipawnbroker` | 6 | `lakshmipawnbroker` |

## Snapshot inventory

| Source schema | Customers | Contacts | Addresses | Loans | Loan items | Payments | Releases | Unreleased loan candidates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `jcl` | 5,882 | 1,898 | 3,997 | 29,019 | 18,522 | 11,085 | 26,474 | 2,545 |
| `jsk` | 646 | 513 | 621 | 5,295 | 5,301 | 3,093 | 3,811 | 1,484 |
| `lakshmipawnbroker` | 2,102 | 1,085 | 2,104 | 11,093 | 11,100 | 8,657 | 8,658 | 2,435 |
| **Total** | **8,630** | **3,496** | **6,722** | **45,407** | **34,923** | **22,835** | **38,943** | **6,464** |

An unreleased candidate is a `girvi_loan` with no corresponding `girvi_release`
row in this archive. It is an admission candidate, not proof of an active,
reconciled operational balance.

The three schemas have the expected legacy source tables: `contact_customer`,
`contact_contact`, `contact_address`, `girvi_license`, `girvi_series`,
`girvi_loan`, `girvi_loanitem`, `girvi_loanpayment`, `girvi_release`, and collateral
support tables. No `girvi_loanitempic` data exists in these three schemas; storage
box rows exist only for JCL (9) and JSK (3).

## Findings that gate admission

1. JCL `girvi_loan:29887` (`loan_id=R09911`) has source `loan_date`
   `2026-12-16 09:47:00+00`, later than the September 21 discovery snapshot. The
   owner confirmed the intended business date is `2025-12-16`. The original archive
   remains immutable; the migration correction ledger must bind this exact source
   identity, original value and corrected value. The final snapshot must verify the
   correction before this loan is admitted.
2. JCL's latest payment and release are `2026-09-04`; JSK's are `2026-09-18`; and
   Lakshmi Pawn Broker's are `2026-09-19`. These are snapshot observations only.
   Live production can change after them.
3. The legacy table shape matches the planned adapter family, but the committed
   adapter's owner rules are JCL-specific. JSK and Lakshmi require their own
   mapping profiles and contract fixtures before a rehearsal.

## Live-source cutover rule

This snapshot supports source-adapter work and an isolated rehearsal. It cannot be
used as the production source of record because customers, loans and releases
continue to change.

For go-live, use this sequence:

1. Rehearse against a disposable RLS destination using an earlier discovery
   snapshot.
2. Schedule a cutover window and stop writes in the legacy application.
3. Take a new complete archive and media manifest after the freeze.
4. Run the same reviewed adapters against that final archive into a fresh
   production destination.
5. Reconcile each Workspace, accept holds explicitly, and only then enable new
   application writes.

There is no incremental replication path in this migration. Building from a single
final snapshot prevents a payment, release or customer created during migration
from being silently missed.
