---
status: active
owner: project
updated: 2026-10-09
tags: [loans, drafts, collateral, numbering]
related: [../domain/loans-mixed-metal-origination.md]
---

# One loan per collateral entry

The owner requests extending the existing saved-draft split with an atomic option
that keeps one collateral entry on the original and creates a draft for every
other entry. The existing selected-item grouping and ordinary draft lifecycle are
retained. No new table, migration, origination channel or financial event is added.

`PawnDraftSplitForm` offers two modes and a retained-entry picker, initially the
first entry. Labels identify descriptions, metal, net weight and principal. Terms
start with the source series, product, date and tenure. JavaScript only hides the
irrelevant selection block; native form submissions work without JavaScript.

`preview_pawn_draft_split` builds one destination group for the existing mode or
one group per moved entry for the batch mode. Ordinary economic resolution supplies
each row and the retained source; review compares combined principal, interest,
deductions and estimated payout with the original grouped draft. `preview_numbers`
checks that the complete batch fits and consumes nothing. Expected numbers are
bound into the confirmation fingerprint alongside item/photo identity, terms and
calculated economics. Changes require another preview.

`split_pawn_draft` authorizes edit/create under explicit Workspace ownership, takes
the Workspace NO KEY UPDATE lock before source/series/sequence/item locks, and
rechecks the preview. It calls ordinary draft creation for each destination,
replaces temporary collateral with the original identities, then updates the
retained source once. One outer transaction includes all loans, counters, item
moves and audit records. Files are retained without re-upload or duplication.

Source `draft_split_out` audit metadata includes the fingerprint, canonical request
hash, original/moved item IDs and destination loan IDs. Each destination has a
matching `draft_split_in` relationship. An authorized identical confirmation
returns the persisted destination loans; altered input is rejected. The bound
form accepts only audited original identities for a completed retry, and preserves
the completed destination series/product even if subsequently stopped/retired.
Authorization remains mandatory on replay. Ordinary successful confirmation
redirects to a result page with links to every loan; refreshing does not resubmit.

Tests cover ten entries creating nine drafts, a different retained entry,
quantity/photo identity preservation, per-loan charges, grouped-mode compatibility,
insufficient capacity, stale item/economics/number previews, partial failure
rollback, request mismatch, unauthorized/cross-Workspace access, HTTP retry after
series stop, and two simultaneous confirmations returning the same drafts.
Local verification artifacts are under `.tmp/draft-split-20261009/`. The preview
database contains fictional unpaid examples only; production rollout is separate.

Verification: 132 regression checks pass in a fresh disposable test database;
two final HTTP/form checks pass after improving the item labels. Desktop, mobile
and no-JavaScript preview/completion checks pass with screenshot review. Localhost
8083 has a fresh unpaid ten-entry example ready for manual testing.
