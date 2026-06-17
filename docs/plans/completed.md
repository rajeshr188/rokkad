---
status: active
owner: project
updated: 2026-06-17
tags: [plans, completed]
related: [../STATUS.md, ../archive/]
---

# Completed Work

## Architecture Cleanup

- Contact stale Girvi loan references were removed or moved behind selectors/facades.
- Contact summary logic was separated from the `Customer` model.
- DEA facade boundaries were clarified and import tests were added.
- Girvi facade was introduced for cross-app reads.
- Girvi dashboard metrics were moved to `GivenLoan` / `TakenLoan`.

## Setup And Posting Fixes

- Rates were exposed through visible navigation paths.
- Rate-source setup became discoverable.
- Rate forms were upgraded with crispy helpers.
- Girvi disbursal handles missing voucher type setup and customer account provisioning through DEA facade helpers.

## Historical Implementation Phases

Archived completed phase notes:

- [Multi-tenant completed phases](../archive/multi-tenant/completed-phases/)
- [Root implementation reports](../archive/root/)
- [Girvi migration/refactor reports](../archive/girvi/)
- [DEA voucher/payment reports](../archive/dea/)
