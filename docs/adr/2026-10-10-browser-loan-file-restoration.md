---
status: accepted
owner: project
updated: 2026-10-10
tags: [adr, portability, staging, loans, rls]
---

# Browser restoration routes supported files to the existing Loans services

The owner accepts the portability review and selects its recommended increments.
One existing Import Loans landing route accepts published history/opening JSONL,
closed-position JSON and supported servicing/closed ZIPs. Bounded profile detection
selects a published parser; it never trusts a filename, uploaded SQL or source
Workspace identity as destination authority.

Keep complete-history batches and financial commands unchanged. Add a small
LoanRestoreBatch for file-based and multi-loan reviews, with direct Workspace
ownership, forced RLS, registry coverage and ordinary PostgreSQL guards. Store
exact source bytes in existing private application storage; metadata and hashes
are staging evidence, not a second loan ledger. Register the file with storage
inventory. Do not copy package media into database JSON/base64.

Importers may stage and prepare explicit destination matches. The canonical owner
or existing platform override performs financial preview/confirmation under the
current Loans access policy. A signed one-hour review binds source, mappings,
batch, actor and Workspace. Domain commands revalidate setup/ownership, reconcile
positions and preserve their own narrower wire limits. Source-local identities
never become destination primary keys. Closed positions ask only for borrower
and series; absent historical terms are not invented.

Completed/cancelled batches are immutable. Cancellation cannot erase accepted
financial evidence; it clears unfinished staged data and deletes the upload only
after transaction commit. Same-file retries reuse the current batch and accepted
domain identities. No notifications, payouts or current valuation decisions are
performed by restoring source records. Whole-Workspace transfer remains a later
explicitly bounded package/continuation capability.

See the [ordered plan](../plans/data-portability-completion-20261010.md).
