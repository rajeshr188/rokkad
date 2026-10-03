---
status: accepted-local
owner: loans
updated: 2026-10-03
tags: [khata, series, lifecycle, audit, rls]
related: [../implementation/khata-series-status.md, 2026-10-01-khata-operator-forms-and-native-recovery.md]
---

# Reasoned Khata series pause and retirement

The owner authorized recommendation seven after action guidance. Existing lending
commands already require an active Khata series for drafts, opening/withdrawals
and limit increases. Availability is distinct from an account's lifecycle and
licence eligibility. Existing account servicing must continue after lending stops.

Keep `is_active` as the existing lending gate. Add a nullable immutable retirement
timestamp: inactive without retirement means paused; retirement is terminal.
Active can pause or retire; paused can resume or retire. Resuming restores only
series availability, not licence eligibility, number capacity or lending approval.
New series start active. Existing inactive rows become paused without invented
past events. No counter rewind, prefix reuse or association-edit control is added.

Use one directly Workspace-owned append-only `KhataSeriesStatusChange` table for
actor/time/reason, consecutive series sequence and request identity. PostgreSQL
validates the current state and transition, then atomically projects availability.
Direct status rewrites, evidence edits/deletes and retirement reversal are refused.
The table has forced RLS, registry coverage and restricted-role isolation tests.
This is setup evidence, not an account financial/custody operation.

Reuse setup administration and current business-write availability. Preview and
CSRF-protected signed confirmation bind Workspace, actor, series, instructions,
today's date and series state/counter/association evidence; reviews expire after
30 minutes. The command rechecks authorization, locks Workspace then series,
refuses stale reviews and returns successful exact retries without applying them
again. Controls explain that all withdrawals and limit increases stop, including
existing accounts. Interest, collateral servicing, reductions and settlement retain
their ordinary permissions and financial/custody rules.

Native exact-identity recovery includes the new table and retirement field. Its
existing strict schema/guard compatibility gate refuses older archives on the
changed schema; retain old archives with their matching frozen image or use full
database/media recovery. Do not silently translate historical status evidence.

The independent Khata migration branches from 0040. A no-operation merge joins
the separately developed ordinary Loans branch in the full checkout. The local
Khata candidate includes only its branch, preserving the previous verified base
and excluding unaccepted ordinary Loans migrations and application changes.
