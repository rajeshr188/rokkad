---
status: accepted
owner: project
updated: 2026-10-08
tags: [billing, pilot, publication, authorization]
---

# Limit initial monthly self-service to JSK

The owner requests completion of the paid rollout and authorizes proceeding with
JSK’s first-payment pilot. Its existing trial ends at 23:39:08 IST on 8 October.
Make the offer visible beforehand, but preserve natural expiry and require the
canonical owner to accept terms and authorize Razorpay payment afterward.

Use the optional BILLING_RECURRING_WORKSPACE_IDS list. An empty list retains
normal all-eligible-Workspace behavior; a nonempty list permits new agreement
creation and authorization only for those IDs. Malformed configuration denies
new operations. Enforce this at the shared creation and authorization services,
including operator calls, plus selected offer presentation and consent recheck.
Recovery, callback verification and cancellation remain available outside the
cohort and while new billing is paused. Existing mandates are not cancelled by
removing a Workspace from the list or disabling creation.

The pilot configuration is recurring enabled, selected monthly binding 1, allowed
Workspace ID 2 only, and generic checkout disabled. Public free trial and account/
invitation mail stay enabled. JSK sees price, capacity, maximum collection count,
cancellation terms and its exact trial end. No consent token or payment action is
issued before expiry. Visiting the page after expiry can issue a fresh signed
review; expiry does not create a mandate or charge automatically.

Public home/pricing/FAQ pages advertise available paid subscriptions only when
selection is valid and there is no named cohort. After first live payment,
invoice, access, receipt and release acceptance, clearing the cohort permits
other eligible existing and new Workspaces to use the same owner flow. Annual,
one-off catalog publication, early trial conversion and automatic replacement
remain excluded. No new model, migration, scheduler or permission is introduced.

Mail continues its existing invitation/account-only scheduled scope during the
pilot. Verify the first paid receipt before widening receipt dispatch. Real owner
payment and delivery acceptance cannot be replaced by mocked automated tests.
