---
status: accepted
owner: project
updated: 2026-09-25
tags: [loans, disbursal, reversals, evidence]
---

# Preserve each disbursal attempt when correcting a loan

The existing correction workflow permits reversing a native disbursal, returning
the approved loan to draft, editing it and approving again. One-to-one policy and
amount snapshots, and a hardcoded schedule version of one, incorrectly prevented
the final disbursal. JSK 06703 exposed this mismatch.

Retain every original event, reversal, approval, policy, amount snapshot and
repayment schedule. Policy and disbursal snapshots belong to a loan through
history foreign keys. PawnLoan holds nullable current snapshot references for
operational readers. Owner migrations populate these references for all existing
loans, including migration openings and renewal successors. Same-loan/workspace
database guards protect the new references; existing forced RLS remains in place.

Under the existing loan row lock, an approved loan may disburse only if no
unreversed native disbursal remains. Create fresh frozen evidence from its current
approval, allocate the next schedule version and switch current references in the
same transaction. Include approval and policy identities in event fingerprints so
equal amounts on the same date can form distinct reversed/replacement attempts.
Schedule content fingerprints describe economics, not attempt identity; retain
source-event and loan/version uniqueness rather than loan/fingerprint uniqueness.
An ACTIVE retry returns its unreversed event without creating anything.

Tranche and interest readers select the disbursal effective at the requested date,
excluding reversals effective by that date. A reversed attempt has no live tranche
balance. Existing reversal schedule termination is retained. Printing follows the
new approval; an earlier issued document remains immutable historical evidence.
The narrow loan-history/1 export still rejects reversal histories explicitly.

Do not repair this error by deleting snapshots, altering old events, resetting
loan numbering, or automatically disbursing the customer's draft. Deployment
requires a server-only backup and a brief stop of this application's old workers
during migration/backfill to avoid old code creating rows without current links.
Once replacement attempts exist, use a compatible fix-forward release; older
one-to-one code and schema cannot represent the preserved history.
