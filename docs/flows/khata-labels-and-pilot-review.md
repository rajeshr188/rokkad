---
status: active
owner: project
updated: 2026-10-03
tags: [khata, operator, labels, pilot]
---

# Khata labels and pilot review

Open a khata and choose **Documents → Collateral labels**. Select one held item,
a combined label for all held collateral, or one label per held item. Issue the
PDF, then print at **actual size / 100%** on 100 x 60 mm stock. The multi-item-page
option still uses one 100 x 60 mm page per item; it is not an A4 sticker grid.

Labels preserve item descriptions, quantities, immutable UUIDs, gross/net weights,
purity, storage and custody at issuance. Combined labels include net totals by
metal. A pending outgoing return is still physically held and appears as
**Return pending**. It cannot back another withdrawal. Already returned items
cannot receive a new custody label. Draft collateral can be labelled after actual
receipt; this neither approves terms nor records a withdrawal.

For a larger account, choose **One label per selected item**. Search by item
number, UUID, description or storage reference. Select individual checkboxes or
use **Select displayed items**, then **Issue label PDF**. Alternatively,
**Print displayed batch** prints exactly the displayed identities without needing
JavaScript. Each batch contains at most 100 labels in ascending item-number order.
Go back and choose **Next batch** for the remaining items; search/page navigation
starts a new selection. The one combined/all-item options still apply to the
whole account and are limited to 100 held items. A newly returned item invalidates
a new batch rather than silently dropping it. Already issued batches always
reprint their original saved membership and bytes.

When a combined label will not fit at 6 pt or larger, choose individual labels.
The application fails rather than remove text or print smaller type. If a single
item still cannot fit, use its full collateral document for identification and
review the print requirements before using that item in the pilot.

Original label issues appear with the other saved Documents. Reprints return the
exact original PDF, including its original custody snapshot, after later exchanges
or returns. Scan the QR to see current custody. Individual QR codes resolve the
immutable item UUID; combined QR codes resolve the account UUID. Staff must sign
in and have workspace data access. The detail page opens its collateral disclosure
and identifies the item, including after a completed return. QR codes are not
public borrower documents or authority to release collateral.

## Read-only pilot assessment

Administrators with export permission can open **Khata accounts → Review khata
pilot readiness**. The page writes no business rows or files. It checks software
and native evidence, then lists the separate manual acceptance gates. A CLI version
uses the restricted runtime settings:

```powershell
python manage.py check_khata_readiness --workspace <pilot-slug> --actor <authorized-admin-user-id> --settings django_project.settings.base
```

Use the deployment's ordinary restricted-runtime settings if different from
`base`. Do not run web/workers with the owner migration/recovery settings. An owner
connection deliberately fails runtime-role safety. A failing check produces a
nonzero CLI exit; even all checks passing does not activate a pilot.

Before a separately authorized named pilot, retain the candidate build identity
and test evidence, complete database/private-media backups and independent checksums,
rehearse restoration in a disposable matching environment, verify restricted web/
worker connections, and print/scan both label modes on the intended hardware.
Retain the printed QR hostname and workspace paths on recovery, or explicitly
forward their original hostname to the restored application.

Review opening, recurring withdrawals, monthly/annual interest, partial receipts,
limit/rate changes, allowed/blocked exchanges, formal reduction returns, settlement
and actual handovers with the workspace's operators. Sign off actual principal,
unused entitlement, interest and custody after every action. Verify that ordinary
JCL/JSK/Lakshmi flexible loans and their numbering/prints remain unchanged.

Review the limits before creating real accounts: only whole interest receipts and
unhanded exchanges have bounded corrections. Mistaken payouts, activated revisions,
settlements and completed handovers cannot be repaired through a generic edit,
balance override, routine backdating or evidence deletion. Agree on the support/
forward-fix process before accepting that scope.

Khata is not included in ordinary pawn pledge books, statutory notices, auctions,
renewals, funding/repledging or old-paper imports. Determine any applicable external
records and default procedures for the named workspace; an independent series is
an application numbering choice, not a claim of regulatory exemption. No automatic
notifications or additional charges/penalties are activated by this slice.

See [the release review](../implementation/khata-release-review-20261002.md) and
[the label decision](../adr/2026-10-02-khata-labels-and-pilot-review.md) and
[selected-batch extension](../adr/2026-10-03-khata-selected-label-batches.md).
