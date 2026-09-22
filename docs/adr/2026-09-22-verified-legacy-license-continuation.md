---
status: accepted
owner: project
updated: 2026-09-22
tags: [loans, portability, licensing, numbering]
---

# Verify an imported license without replacing its series

The owner needs to originate new loans in the existing licenses and series after
the final Linode import. The September 12 unknown-evidence decision deliberately
made legacy references inactive and prevented their conversion. Recreating series
under another license would fragment the register and risk overlapping numbers.

## Decision

For an imported reference that actually identifies the same legal license, allow
one explicit verification through the setup-administration service. Require current
validity dates, issuing authority, a matching license document, the final source
SHA-256/date/report reference and confirmation that imports are complete and the
old system has stopped issuing numbers. A source grouping that is not the actual
legal license number must remain a reference; configure a separate verified license.
The application records this operator assertion; it does not independently certify
the document, validate government records or stop the old server.

Append an immutable `VERIFICATION` revision with document hash, actor and structured
numbering evidence. Then update the current license projection to verified/active
in the same transaction. Keep the license ID, every series ID, formatting, active
state, prior revision and every loan's frozen revision FK unchanged. No number,
loan, interest or cash movement is issued by verification.

Review both counters in every series, including closed/cancelled/excluded source
records. Never lower an existing reservation. Reject missing counters, out-of-range
values, overlapping numeric prefixes and a reviewed range that omits existing
destination numbers. A digest detects changes to sequence settings or counters
since form load. Lock the workspace (as import setup does), license, series and
sequences; reserve through the reviewed values before storing the evidence.
An exhausted sequence remains exhausted; continuation does not extend its ceiling.

Migration `loans.0015_license_continuation` narrowly replaces the old conversion
guard. Direct flag flips still fail, verification needs complete document/source
evidence and matching reserved counters, and revision update/delete guards and
forced RLS remain. Disbursal is blocked when the loan's frozen revision is
`LEGACY_REFERENCE`, even after its current license has been verified. The migration
does not activate existing data and is deliberately forward-only: restoring old
guards after a verification would contradict the supported evidence chain.

This supersedes only the absolute prohibition on reference conversion and the
requirement for separate verified setup in the September 12 ADR. Original import
and restore mapping checks continue to require legacy references when their source
evidence says validity is unknown. Finish imports before verification; an archive
restore of old evidence uses corresponding reference setup, not the verified
projection. Export and servicing continue to use frozen loan evidence.

## Cutover acceptance

The final frozen dump and complete number register are operator inputs. The live
September 21 rehearsal is not proof of the later cutover counters. Review all
three workspaces after final data/media reconciliation; verify licenses only then.
Product activation, calculation policies, current prices, membership and ordinary
approval/disbursal checks still apply. Rehearse creating, approving and disbursing
a new loan in an isolated copy with the reviewed next number; never create a fake
loan in the accepted production destination to prove readiness.

See [operator flow](../flows/legacy-license-continuation.md) and
[cutover runbook](../implementation/linode-production-cutover.md).
