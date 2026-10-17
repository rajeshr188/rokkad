---
status: in-progress
owner: project
updated: 2026-10-17
tags: [loans, origination, numbering, release]
related: [approval-numbering-20261017.md, business-lending-terms-20261017.md, closing-navigation-review-20261017.md]
---

# Origination, numbering and navigation release

The owner authorized committing, pushing and releasing the reviewed local work.
The candidate includes Business lending terms and narrow amendments, independent
New loan entry preferences, permanent numbering at first approval, the bounded
paper reference simplification, one Releases navigation and searchable closing
loan/Party relationship selectors. Drafts cannot print loan tickets. Existing
issued numbers, frozen agreements and current monitoring rules remain intact.

Preserve unrelated WhatsApp work, dirty source checkouts and JSK WH02306. This
release does not authorize customer corrections, policy amendments, subscription
changes, outbound messages or provider activation.

## Compatibility and promotion gates

Loans 0093/0094 and data_portability 0032 require matching web, worker and scheduled
reader code. Profile-5 setup packages retain independent preferences; previous
published profiles retain their meanings. There is no loan/number backfill.

Require exact committed-source CI, migration rehearsal and restricted-role checks,
pre/post encrypted backups using the existing approved R2 job, exact application
recovery, separate static assets and read-only production acceptance. Pause writes
and scheduled readers for owner-only migrations and the coordinated switch.
Before reopening, verify existing identities, agreements, policies and financial
positions. An application-only rollback is unsafe after unnumbered drafts or
profile-5 receipts exist; recovery must retain the matching database/application
boundary and must never silently discard later business transactions.

## Evidence

The initial local broad snapshot ran 2,806 tests with failures. All 45 distinct
failing cases pass together on final-code reruns. Separate final checks pass 38
print/document tests and 12 page checks, 17 allocation/concurrency/migration tests,
and seven frozen export-contract tests. Earlier setup/navigation integrations and
their overlapping selections are recorded in the linked implementation notes.
The authenticated loopback review uses fictional data and restricted runtime
credentials; its database and scratch artifacts are excluded from the release.

Release source, exact CI, production preflight, recovery, backup, migration and
promotion results will be recorded here as they are verified.

The initial candidate is `ce1b14fe` (formatting baseline `80c2712b`). Its Linux
boundary suite found one stale sidebar assertion for Completed closures. The
follow-up checks one Releases destination and continued data-view authorization;
all five local preference/navigation tests pass. Formatting is separate again.

The schema-only production rehearsal identified a legacy ownership mismatch:
`public.portability_business_package_guard()` belongs to the bootstrap role,
whereas ordinary production migrations use `rokkad_prod_owner`. Promotion must
align this one invoker-security function with the existing migration owner and
verify that ownership alignment alone preserves its definition. Application
runtime authority is unchanged. The rehearsal uses schema and migration metadata
only, with zero customer rows, and checks upgrade/reverse/re-upgrade before release.

The exact-source `b8bad4dd` CI run completed 2,813 Loans tests with one stale
assertion: the owner preflight expected a composite foreign-key error when moving
a parent loan between Workspaces. Loans 0094 now rejects that move earlier through
the stronger parent-identity trigger. The assertion follows that guard; independent
adversarial tests still exercise the composite references. No application or
migration behavior was relaxed. A new complete exact-source run is required.
