---
status: accepted
owner: project
updated: 2026-09-25
tags: [loans, release, transition, evidence]
---

# Record paper closures separately from counter collections

The owner approved a fast transition workflow for all three branches: paper-first
closure entry now, followed by branch-specific retirement after staff move to
direct system releases. The existing 20-loan counter batch represents one combined
payment today, so it must not be repurposed to claim unrelated paper collections.

Add a PAPER mode to the existing immutable batch/line evidence, with up to 50
loans per submission (subject to measured acceptance), a common actual closure
date, shared optional paper reference, and per-loan cash, payer, recipient,
reference override and explicit authorized interest concession. Use the ordinary
release writer; preserve principal/fee conservation, custody, schedules, numbering,
newest-first reversal and RLS. Selected rows commit atomically. Signed ten-minute
reviews, fresh authorization and row locks protect concurrent or stale submissions.
Unselected rows remain on the entry screen; this is not a persistent draft system.

Today, calculated due and borrower identities are defaults, not evidence. One
explicit confirmation attests the selected collections and completed handovers.
Date changes require recalculation and confirmation. Earlier entry cannot precede
origination or later financial/custody activity. Imported servicing remains
strictly after its opening date. Native completed accrual periods still require
finalization through the existing workflow; unsupported chronology is blocked.

Paper records normally attest only a day. Preserve release.effective_date and
recording timestamps independently, and use null release-item returned_at rather
than fabricating an exact historical handover time. Immutable release payloads
identify paper-closure/1 and DAY precision. A database guard allows unknown return
times only with that evidence. Existing release timestamps are unchanged.

PaperClosureTransition is directly Workspace-owned, uniquely scoped and forced-RLS
protected. Only the canonical owner action changes system-first date/retirement,
with reason and audit. Staff may clear earlier backlog after system-first starts;
on/after that date, or after retirement, entry requires settings-administrator
authority and a reason. No automatic deadline or cross-branch transition. Settings
and submissions serialize on the same row so retirement applies at commit review.

Counter release semantics and its 20-loan limit remain unchanged. History identifies
both modes. Paper CSV is an authorized reconciliation report, not a restore package.
Current strict history/opening restore profiles cannot preserve date-only return
and all per-line paper evidence; reject their export explicitly for these histories
instead of truncating evidence or inventing timestamps. Database backups preserve
the complete graph. A future versioned portability contract must include paper
evidence before offering round-trip package export.

Deploy with server-only backup, owner migration and restricted-runtime checks.
Once paper records exist, rollback must retain support for unknown return times;
never delete new closures or restore an older business snapshot to revert code.
