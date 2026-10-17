---
status: active
owner: loans
updated: 2026-10-17
tags: [contracts, portability, setup, preferences]
related: [fresh-business-setup-v5-rows.json, ../implementation/business-lending-terms-20261017.md]
---

# Fresh business setup version 5

`rokkad-business-package/5` uses setup version 5 and the existing bounded package
review, checksums, actor/Workspace authority, media handling and atomic restore.
Version 5 adds current independent New loan screen preferences to version 4.
The published [row inventory](fresh-business-setup-v5-rows.json) is explicit;
versions 1–4 are unchanged and must not silently export these preferences.

The additional `loans.LoanEntryPreference` row contains source-local id,
optional `license_id`/`series_id`, `purpose` and `updated_at`. Purpose is DIRECT,
PAPER or INHERIT. Register scope requires its owning licence. References must
resolve within the same package; restore validates model/DB scope and uniqueness
under destination Workspace isolation. Source IDs are remapped and the restoring
actor is recorded as updater, using the existing setup actor-remapping convention.

The preference applies to current presentation. It is not historical lending
authority, contractual repayment behaviour, a current monitoring policy or a
source financial transaction. Explicit INHERIT intentionally follows the broader
preference even when legacy financial configuration at that scope contains a
different entry default. Financial-policy fields remain retained evidence.

Export selects version 5 whenever an independent preference exists. Exact
Workspace recovery retains its separate complete schema-bound model inventory;
portable setup is not native database recovery. Package receipt profile support
cannot be removed while retained version-5 receipts exist.
