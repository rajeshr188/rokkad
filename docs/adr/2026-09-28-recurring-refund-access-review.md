---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, subscriptions, refunds]
---

# Review recurring refunds through the existing billing decision

Full refunds already preserve invoice/cycle evidence and leave access unchanged
for explicit review. The existing BillingResolution owner workflow now dispatches
recurring invoices to a cycle-aware Test Mode service. It does not issue refunds,
cancel provider agreements or release their Workspace reservation.

Before a first decision, require an active current owner/platform actor, explicit
Workspace and Test Mode binding, matching fresh invoice/payment/plan/agreement
evidence, a fully refunded provider payment, and fresh processed provider records
for every saved refund. Under the Company lock, recheck authority, Subscription
revision and matching local full-refund totals and identities. Store the existing
immutable BillingResolution plus Subscription and Agreement audit events atomically.

`retain_access` preserves all current Subscription fields and entitlements. For a
refunded future hold it closes the access review without applying the period.
Provider refund checks still prevent later held-period application. The dashboard
shows the refund decision rather than continuing to request access review.

`end_access` requires a freshly verified terminal provider agreement and the exact
current, started, unexpired applied cycle. Its plan/end must still match the
Subscription and latest access-grant event. Any other unreturned paid cycle ending
in the future blocks the action, including an unapplied future hold. End access
through the existing cancelled/read-only transition without rewriting purchased
dates, immutable cycle evidence or entitlements. This does not affect Workspace
lifecycle or bypass independent platform access decisions.

Replay returns the same decision without provider mutation or access reactivation;
a different decision is rejected. Partial refunds, unrelated/newer/expired periods,
stale revisions, provider outages and mismatches remain review cases. Existing
one-off review rules are unchanged. No schema change or production activation.
