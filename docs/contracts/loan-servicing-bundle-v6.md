---
status: active
owner: loans
updated: 2026-10-15
tags: [portability, loans, corrections]
related: [loan-servicing-bundle-v5.md, ../adr/2026-10-15-shared-loan-fact-corrections.md]
---

# Loan servicing bundle version 6

`loan-servicing-bundle/6` preserves version 5's exact agreement Party references
and underlying financial profile (versions 1–4), and additionally accepts
`COLLATERAL_CORRECTED` LoanChangeLog rows with `collateral-fact-correction/1`
metadata. Earlier profiles refuse this evidence, including metadata disguised as
an ordinary change-log event. Their schemas and row inventories are unchanged.

Each correction identifies one existing source-local PawnCollateralItem owned by
the same loan and Workspace. Before/after values contain exactly description,
quantity, metal, gross_weight, net_weight and purity_percentage. Decimal values
are canonical four-place strings; quantity is an integer or genuinely unknown;
gross may remain unknown. Known quantities/gross weights cannot become unknown.
The record retains actor, unchanged ACTIVE/CLOSED state, reason, supporting
reference, request identity/hash, reviewed source fingerprint, whether measurements
changed and the highest appraisal version present at review. Subsequent corrections
must form an unbroken chain ending at the current item projection.

Destination restoration remaps the item ID, recomputes the local request hash,
and retains the source item/hash/Workspace claim. Appraisal version cutoffs remain
valid after destination timestamps are assigned. Original approval/disbursal,
recording, source attachments and issued documents remain separate immutable
evidence. When inserting a recorded payout snapshot, restoration temporarily
projects its genuine original collateral facts for the ordinary Python/SQL
checks, then restores current corrected facts before accepting the destination.
No guard is disabled. Preview is rolled back, confirmation is bounded/idempotent,
and source/destination positions must reconcile under the established contract.

Exact Workspace recovery retains all original correction rows and identities.
Retained version-6 restore or correction evidence prevents unsafe downgrade.
