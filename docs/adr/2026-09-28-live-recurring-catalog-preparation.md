---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, recurring, catalog, provider-mode]
related: [2026-09-28-explicit-billing-provider-mode.md, 2026-09-27-recurring-agreement-evidence.md]
---

# Prepare live catalog mappings separately from recurring charges

Live billing preparation needs a verified mapping between an existing Razorpay
plan and Rokkad's price, currency, cycle and entitlements before any mandate can
be authorized. Allow the existing platform-only catalog binding service to accept
an explicit `mode="live"`; keep agreement creation, owner authorization, recovery
and cancellation Test Mode only for now. This narrowly extends the catalog part
of the original Test Mode agreement decision, without activating live recurring.

`prepare_recurring_agreement bind --mode live --preview` fetches one explicitly
known provider plan through GET, validates its amount/currency/interval against
the local offer and reports only local commercial terms. It writes nothing.
Without `--preview`, the same verification registers the existing immutable
RecurringPlanBinding with actor and reason. Repeating identical terms returns
the same binding; changed terms require a new provider identity. The operator
cannot create a provider plan, mandate, charge, invoice, paid time or receipt
through either catalog operation. There is no new schema or provider POST.

Live preparation requires matching explicit live configuration/credentials and
both checkout and recurring authorization paused. It refuses stored bindings from
another mode and test/unclassified one-off invoices before contacting the provider,
and rechecks evidence before saving. Offer changes during the fetch are refused.
These checks do not make concurrent mixed-mode processes supported: never run
test and live billing against the same database or promote the populated rehearsal
database. Existing local commercial snapshots and legacy evidence are not rewritten.

Test registration retains its existing activation flag and Test Mode credential
requirements. Test preview can run while new authorization is paused; both catalog
modes refuse conflicting bindings. Platform authority and a nonempty reason remain
required, including previews. Actual live plan creation/binding still needs reviewed
commercial terms, protected live credentials and a separately prepared production
database/deployment. This increment does not select tax treatment, mandate duration,
publish prices or approve a paying pilot.

Provider contract checked 28 September:
[fetch an existing plan](https://razorpay.com/docs/api/payments/subscriptions/fetch-a-plan/).
Its GET response supplies the plan identity, interval, period, amount and currency.
Live behavior is tested with mocked provider responses; no real live request or
catalog registration has been performed.
