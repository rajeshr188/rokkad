---
status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, setup]
---

# Prepare historical Loans setup

Open **Import Loans** from Loans setup, then **Check historical setup**, or use
the preparation link on the Party import page. This
owner-only step checks existing destination setup for one historical loan and
previews local numbers. It does not upload, save, reserve or import anything.
The separate [JSONL upload workflow](loans-history-import.md) provides financial
validation, reconciliation and explicit commit.

For the previous schema-based application's PostgreSQL dump, first use the
[offline legacy source preview](legacy-dump-preview.md). It reviews source records
without importing them or binding destination setup. Its reports are not files for
the canonical complete-history upload form.

Enter the stable source namespace UUID, source loan ID and original number.
Keep the namespace and ID unchanged when retrying the same source loan. Copy the
original licence number, disbursal date, tenure, calculation contract version and
operational grace from source evidence; do not guess missing facts. For a fully
released loan, also enter both its source release ID and original release number.
An active loan leaves both release fields empty. This form is source-format
independent; it does not itself parse canonical files, CSV or Excel.

Select an existing destination licence revision, a series belonging to that
licence and a compatible flexible partial-payment product version. The revision
must match the source licence number and cover the original disbursal date. The
product must match the source calculation contract, grace and tenure; its dated
availability must cover that date. Draft or other repayment structures fail.
Retired versions and inactive/expired setup can represent historical facts without
being reactivated or authorized for new issuance. Passing these checks is not a
validation of interest calculations, financial events, custody or a whole history.

Choose **Check setup and preview numbers**. Proposed numbers use a separate
historical namespace based on source identity; the original number is shown
alongside. Existing destination conflicts and configured future sequence overlaps
fail explicitly. A match is not assumed to be a safe retry until the historical
importer verifies source identity and completed evidence. Live counters do not
advance. The displayed result is neither a reservation nor a commit approval;
the historical importer must recheck source data, setup and conflicts under locks.
No result is saved, and future setup/numbering changes can invalidate it.

Current access requires matching Workspace context, canonical ownership and
membership (or the existing platform override), data view/import and Workspace
settings permission, ACTIVE Workspace lifecycle and normal HTTP commercial access.
Every GET/POST rechecks access; POST requires CSRF and responses are not cached.

Next: complete-history staging, validation/reconciliation and approved historical
commit, followed by canonical export. Both active and fully released loans remain
in the selected [contract](../contracts/loan-history-mvp.md). Renewals, auctions,
missing-history openings and the Party history filter remain outside this slice.
