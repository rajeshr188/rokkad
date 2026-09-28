---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, catalog, publication, pilot]
related: [2026-09-28-live-recurring-catalog-preparation.md, ../plans/monthly-billing-pilot.md]
---

# Keep operator-prepared billing plans private during pilot preparation

An active Plan can be prepared for recurring binding without being an offer to
every Workspace. Previously the owner catalog listed every active Plan even while
checkout was paused, including an automatically populated annual price and legacy
feature claims. This could publish unreviewed terms during monthly pilot setup.

Use the existing self-service switches: when both `BILLING_CHECKOUT_ENABLED` and
`BILLING_ALLOW_TRIAL_START` are false, the plan-list query returns no plans and its
template displays only guidance to Recurring payments and the billing dashboard.
`BILLING_RECURRING_ENABLED` does not publish the generic catalog. An operator-prepared
agreement already supplies the owner-scoped, immutable price, cycle, seller, seats
and collection count; retain that page as the pilot offer and authorization path.

Explicit self-service checkout retains its catalog and annual prices. Trial-only
signup may show eligible plans but does not advertise an annual purchase. Enabling
either self-service switch is therefore a catalog-publication decision and requires
review of every active plan first. This is intentionally not a general per-plan
publication system or a new billing-cycle entitlement model.

Live catalog preview and binding now require trial signup paused as well as checkout
and recurring authorization. Reject an enabled trial switch before provider access
and at the existing pre-save recheck. Test Mode catalog behavior is unchanged.

Remove inferred feature/operation/support comparisons from generic plan cards, and
legacy warehouse/feature claims and estimated overage charges from the dashboard.
Keep member-capacity guidance, current subscription details and actual invoices.
No stored price, annual fallback, entitlement, limit, access date, payment or receipt
is modified. No migration or financial-policy change is required.

The selected pilot keeps checkout and trial signup false, uses one monthly binding,
and requires separate owner authorization after transition/provider acceptance.
Deploy this change paused before saving the new pilot plan. Existing trials,
including JSK's unexpired trial, remain unchanged.
