---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, invoices, seller, tax, immutable-evidence]
related: [2026-09-28-mode-matched-live-recurring-workflows.md, ../plans/monthly-billing-pilot.md]
---

# Freeze the live invoice seller and require explicit tax configuration

The selected monthly pilot uses an individual seller and a proposed unregistered
GST treatment. The previous implicit 18% setting and invoices without a seller
cannot establish the intended live commercial terms.

Require explicit `BILLING_TAX_RATE`; its base default is empty. Tests and the isolated
rehearsal retain explicitly illustrative 18%. Live catalog preparation, new one-off
orders, recurring creation and owner authorization additionally require nonblank
`BILLING_SELLER_NAME`, `BILLING_SELLER_ADDRESS`, and
`BILLING_SELLER_TAX_STATUS=unregistered`, with tax rate zero. Registered-supplier
invoicing is outside this increment and fails closed. Configuration does not decide
whether GST registration is legally required or certify launch readiness.

Store a `seller` object (name, address, tax_status) in new live checkout and recurring
plan snapshots. The existing database guards make these immutable. Recurring paid
cycles already copy the binding's snapshot to invoices; reuse that mechanism.
No new table, migration, evidence backfill or current-settings fallback is needed.

New authorization checks the saved seller against the current reviewed profile.
Missing/stale seller evidence needs a new catalog review. Existing one-off checkout
identity retries return the saved order, and matching-mode confirmation, recovery,
cancellation and paid-cycle recording continue using saved evidence even if seller
settings are removed or changed. Financial truth must survive a configuration issue.

Invoice HTML/PDF and receipts render only the saved seller. An unregistered invoice
shows “GST not charged - supplier not registered under GST.” It does not imply an
exempt or zero-rated supply and contains no personal PAN. Conflicting saved tax and
seller data is rejected. Historical invoices without a seller retain their recorded
GST amounts/wording and never acquire today's seller or no-GST statement.

The PDF uses ReportLab flow layout for wrapping seller/buyer text and prints saved
amounts and billing-period evidence. Checkout and recurring consent show the same
issuer/tax treatment. The test receipt label remains mode-specific.

Deployment/configuration and final business facts are separate: this code change
does not publish prices, install a seller profile, enable dispatch or authorize a
charge. Monthly-only pilot scope still uses an explicitly monthly binding,
operator-prepared agreements and paused one-off checkout. No new plan/cycle gating
framework or general GST engine is introduced.
