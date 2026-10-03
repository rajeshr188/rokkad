---
status: active
owner: project
updated: 2026-10-03
tags: [khata, operator, recovery]
---

# Service a khata and recover native evidence

For the complete staff journey, account figures, worked examples and developer
contracts, start with the [Khata account workflow](khata-account-workflow.md).
Combined receiving/photos and searchable exchange selection are described in the
[usability checkpoint](../implementation/khata-collateral-usability.md).

From **Loans → Khata accounts**, administrators can create a separate khata
series. Leave the licence blank for an independent series. Its prefix must differ
from ordinary-loan numbering. Association and number format freeze after issuance.
The workspace owner chooses **Allow with warning** or **Disallow** for exchange
shortfall/LTV breaches and overdue-interest risk operations; warnings are defaults.

Choose **New khata draft**, select a workspace borrower and series, enter the limit,
monthly percentage rate, LTV, monthly/annual collection frequency and lender
identity. Review and confirm to reserve a permanent number and save proposed terms.
Annual collection still uses the entered monthly rate. Saving is not approval,
interest commencement or cash payout.

Open **Service this khata** on its detail page. Receive actual collateral with
weights, purity, quantity, storage reference and the person delivering it. Attach
photos on the same receiving screen, or attach them later. Missing mandatory photos
allow drafts but prevent approval. Approve opening, then review and record the
first actual withdrawal with its payment reference. This opens the agreement and
starts interest on the full agreed limit, including the original first-month minimum.
Further withdrawals require unused entitlement and adequate eligible collateral.

For interest, review the actual receipt amount and its oldest-due allocation.
Only due completed periods can receive payment. Completed monthly charges may
also be finalized without recording cash; annual accounts retain anniversary dues.
Accrued unpaid and due interest remain separate on the detail page.

For a limit/rate change, propose today's terms and a reason. After opening, LTV,
frequency and lender identity stay fixed. An approver reviews principal repayment
and optional reduction returns, then records the borrower's consent reference.
An authorized approver activates a noncash change; an authorized cashier activates
a repayment with its actual reference. Returns additionally require release access.
Approval alone never changes live terms or authorizes cash collection.

For an exchange, receive the replacements first, then select outgoing and incoming
items using the searchable group tables. Selections survive paging/search and a
trip to **Receive replacement collateral**. Review current approved valuations and
any shortfall/overdue warning.
Same-metal rules still apply. Confirmation reserves the outgoing collateral;
it no longer backs withdrawals but stays physically held. **Hand over reserved
collateral** records the actual item, reservation source, recipient and reference.
Reduction returns require sufficient retained LTV and cleared due interest even
under warning policy. Unopened items have a separate actual-return operation.

For full settlement, review principal, all unpaid interest through closure and
the total to collect. Confirm only after receiving the referenced payment.
Interest stops and remaining items become return-pending. Complete their actual
handovers to close custody. Administrators can review only the supported receipt
or unhanded-exchange correction; reasons and actual refund/nonreceipt evidence
are required. Unsupported historical corrections remain refused.

Every review expires after 30 minutes or at a business-day boundary. Changed
evidence requires review again. Repeated confirmations retain the original request
UUID and do not duplicate cash or custody. Photos and PDFs use authenticated private
routes, never public storage URLs.

Selected collateral labels are issued in batches of at most 100 saved identities;
see [the label workflow](khata-labels-and-pilot-review.md). The native inventory
stays fourteen tables, but the selected-label guard changes its fingerprint.
Restore older native archives with their matching image/schema, then migrate
forward; full database/private-media recovery remains the other recovery boundary.

## Exceptions and support

Open **History** and select an operation number. Its exact-source view explains
whether the type supports correction review, is already corrected, belongs to a
settled account or is blocked by later operations. Links show up to ten exact
blocking sources with the total count. These are read-only diagnostics, not a
promise that cash/custody or current-price conditions will pass confirmation.
An authorized administrator with workspace write access sees **Review correction**
when the scope/dependency checks permit review; this opens the form with the source
selected. Refused form previews also provide links to the blocking sources.

| Situation | Supported handling |
| --- | --- |
| Whole interest receipt was never received | On an ACTIVE account with no blockers, review NOT_RECEIVED with actual reason/reference. Original receipt remains; dues are restored. |
| Entire interest receipt was actually refunded | Review REFUNDED with evidence of the full real refund. A promised/partial refund is not sufficient. Re-record any valid receipt separately. |
| Exchange needs cancellation before outgoing handover | Review current eligibility/prices and hard retained LTV. Original outgoing membership is released logically; incoming replacements become reserved for their separate actual return. |
| Later operations or pending correction returns block the source | Review the linked operations. Only genuinely independent eligible whole receipts may unwind newest-first with real cash resolution. No automatic chain undo. |
| Payout, accepted collateral facts, activated revision, settlement, completed return, partial refund, correction-of-correction or settled/closed account | No supported correction screen. Record the discrepancy and obtain a reviewed support resolution; do not improvise financial/custody events. |

The operator records workspace/khata number, source operation ID, expected versus
recorded facts, actual cash received/paid/refunded, actual custody and any relevant
payment/consent/handover evidence. The workspace administrator checks source and
later-operation links, current account state and existing correction permissions.
For unsupported cases, send that summary through the agreed private support
channel (`support@rokkad.com` is available in the in-app guidance). Sending a
request itself makes no financial/custody change and is not a refund promise.

Support retains the source identifiers and agrees a supported resolution with
the owner. Further compensating commands need defined amounts, interest dates,
entitlement/custody effects, dependency and permission rules, idempotency and
isolation tests. Until that exists, retain the original evidence. Do not edit
posted rows, fake a fresh payout/refund/physical return, restore a backup over live
data to erase a mistake, or claim an unsupported case is corrected.

## Native disaster recovery

The register's native backup download includes **all** workspace khata evidence
and original media, independent of filters. The response includes
`X-Archive-SHA256`. For an operator backup with a visible checksum:

```powershell
python manage.py khata_recovery export --workspace <slug> --actor <authorized-user-id> --file <private-new-backup.zip> --settings django_project.settings.migration
```

Keep the reported checksum separately from the ZIP and protect both as private
financial records. The command never overwrites an existing backup. This bounded
archive supports at most 50,000 khata rows and 256 MiB of expanded manifest/media.
Use full database/private-media backup for larger recovery or prerequisites.

Restore first into an **offline recovery environment**, with the complete database
prerequisites recovered, matching source workspace identity, and no khata rows for
that workspace. Stop writes for recovery. Never clear a live workspace to make it
eligible. Original borrower/staff/licence/rate identities must match. This does not
import old paper accounts, clone workspaces, merge existing khatas or recreate cash
events with today's dates.

Preview uses the table-owner connection and actually inserts/reconciles inside a
rolled-back transaction. It writes no files:

```powershell
python manage.py khata_recovery restore --workspace <slug> --actor <workspace-owner-user-id> --file <private-backup.zip> --sha256 <independently-retained-sha256> --settings django_project.settings.migration
```

Review the row/media counts and restored principal, unused entitlement, interest
schedule and held/eligible custody. Commit the same trusted backup only after the
recovery review, adding `--commit --confirm-workspace <slug>`. The runtime database
role cannot perform a restore. Owner credentials must never run web/workers.

Recovery preserves timestamps, source IDs, UUIDs, complete JSON evidence, document
payloads and original bytes. Existing identical media can be retained; conflicting
media and existing khata rows cause refusal. Failure rolls back all rows/trigger
state and removes only new files. Khata PK sequences advance monotonically;
ordinary-loan counters stay unchanged. Verify the restored application and re-export
the evidence before bringing the recovered environment into service.

This is a trusted disaster-recovery backup contract, not validation of edited or
third-party financial payloads. It does not replace complete database/media backups
or authorize a production restore. See the [decision](../adr/2026-10-01-khata-operator-forms-and-native-recovery.md).

## Pending return selection

Use the account's **Collateral ? Pending returns** browser to identify the actual
item, photograph and source before handover. Its per-item link preselects the source;
the searchable handover form also pairs an item to its active reservation. Staff must
still supply actual recipient/reference and review/confirm. A returned or corrected
reservation may disappear between search and confirmation; reselect and review,
never bypass the service checks. Reduction/photo selectors retain ordinary dropdown
fallbacks; see the [account workflow](khata-account-workflow.md#searchable-pending-returns-and-servicing).
