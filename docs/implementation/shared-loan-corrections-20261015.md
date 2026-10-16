---
status: implemented
owner: project
updated: 2026-10-16
tags: [loans, corrections, collateral]
related: [../adr/2026-10-15-shared-loan-fact-corrections.md, ../flows/loan-journey.md, ../contracts/loan-servicing-bundle-v6.md]
---

# Shared loan fact correction

The owner approved contextual correction navigation and a shared collateral
transcription correction after reviewing when a loan is editable.

Drafts keep their ordinary editor. Approved drafts return to preparation and need
fresh approval. Active/closed ordinary loan detail offers a contextual Correct
menu, with borrower correction on active loans, collateral links per item, and
existing agreement/financial review commands. The former correction chooser URL
redirects to the menu; duplicate standalone paper terms/history links are removed.
Paper receipt rows can open the existing historical review with that receipt
selected. Book-completeness verification remains a separate evidence task.

The new collateral service uses existing LoanChangeLog rows, a signed one-hour
review bound to Workspace/actor/input/current evidence, aggregate/item locks,
explicit confirmation and identical-retry protection. It supports existing item
description, quantity, metal, gross/net grams and purity on consistent active and
closed direct, paper, accepted-history and opening agreements. It keeps item IDs,
source documents, financial events, allocations, principal/rates, custody and
lifecycle unchanged. Missing known facts cannot be erased through this flow.

Measurement/quantity changes make prior appraisal versions inapplicable until a
new approved appraisal is recorded. Calculated metal values use current corrected
measurements; monitoring thresholds and interest remain unchanged. Financial
coverage is not invented, and a Rokkad-only capture checkpoint notices changed
collateral through its existing fingerprint. A description typo retains appraisal
applicability. Old issued document artifacts remain available; new ticket copies
project corrected facts with an explicit correction audit reference.

Loans 0078 adds the correction enum, append-only/foreign-item checks, a request
uniqueness index and protection against losing corrected item identities. Data
portability 0028 admits servicing profile 6; earlier profiles keep their meaning.
These are owner-only migrations. Ordinary readers/writers remain restricted.

Connected renewals, funding reservations/pledges and auctions are held for connected
reconciliation. Adding/removing collateral, actual exchanges, debt reassignment,
unsupported financial restatement and editing verified closed-position admissions
are not silently implemented as transcription. Ordinary newest-first reversals
and historical financial reviews retain their guards; origination reversal cannot
discard a retained collateral correction by returning to an editable draft.

Local verification is complete:

- The final 353-case regression selection passes (462.104 seconds), covering
  ordinary corrections, all four admission paths, servicing, monetary/physical
  preservation, original documents, portability, exports, pledge book and settlement.
- Two final document/recovery cases pass: a corrected ticket obtains a new issue,
  repeated printing returns the same corrected artifact, original issued bytes
  remain exact, and offline exact recovery retains all original Loans rows.
- Version 6 export/preview/restore/re-export passes for direct, paper, accepted
  history and opening loans. The paper case includes subsequent financial terms
  correction, with both histories retained. Old profiles refuse the new evidence.
- Restricted-role posting, foreign item/Workspace refusal, immutable correction
  evidence, stale/competing reviews, identical retry, rollback, unchanged approval
  and payout evidence, closed correction, subsequent settlement and renewal pass.
- Existing native/imported layout browser cases pass. Twelve direct/paper detail,
  form and review captures at 1440/390 pixels pass without JavaScript errors or
  horizontal overflow; menu anchors work in Classic and Tabs. Representative
  desktop/mobile captures were visually inspected.
- Django checks and migration state agree; tracked/new Python import boundaries,
  current documentation links and whitespace checks pass.

Evidence is retained under ignored `.tmp/loan-corrections-20261015/`, including
`release-checks.log`, `documents-final.log` and `ui/checks.json`. These cases use
fictional local fixtures and local/in-memory storage. No real loan was corrected.
The isolated test database was removed after verification; proof artifacts remain.

This collateral implementation has made no production changes. The 16 October
combined pre-commit agreement/collateral/Party-merge/document selection passes
100 tests; see the
[combined acceptance](shared-agreement-financial-corrections-20261015.md#16-october-combined-git-publication-acceptance).
Release needs owner migrations Loans 0078 and
portability 0028 and compatible web/monitoring readers before new correction writes.
Connected graph correction and wider economic restatement remain their explicitly
documented reconciliation boundaries; this does not make every financial event
editable or replace the existing financial correction services.
