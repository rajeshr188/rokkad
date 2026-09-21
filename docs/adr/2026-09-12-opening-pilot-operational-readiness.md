---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, migration, usability]
---

# Recognisable and usable opening loans

The C00121 rehearsal exposed a gap between committing valid opening evidence and
delivering an operational loan. The user authorised finishing this single pilot
before tenant-wide conversion. Dump-specific extraction stays in the one-time
adapter; Loans owns numbering, collection, monitoring and document behaviour.

Opening setup accepts optional `local_loan_number` (nonempty, at most 64
characters). An adapter can explicitly propose the original readable number.
Preview and commit check existing numbers and future sequence ranges; conflicts
require reviewed mapping rather than silent replacement. The number participates
in the approved document digest. Omitting it preserves older input semantics and
exact retries. Source namespace/key remains the import identity. This extends
[historical setup](2026-09-12-loans-history-setup-preview.md).

An owner-only Loans command can adopt the source number of an ACTIVE opening
which still has its generated number, has no later financial events and no issued
loan documents or printed collateral labels. It locks the destination/loan,
checks uniqueness and future ranges, and records the before/after in AuditLog.
Financial events, accepted source documents and original import summaries are
never rewritten. An identical retry is a no-op. This is not arbitrary renumbering
of serviced loans.

The ordinary detail page offers full collection/release for opening loans and
shows the actual dated release quote, original maturity/grace and opening balance
provenance. It does not offer unsupported native repayment/accrual/renewal actions
or call native accrual preview merely to generate an expected error. Server-side
guards remain authoritative. Native loan actions are unchanged.

Monitoring is destination configuration, separate from interest evidence. Test
thresholds require the owner's choice; an absent current appraisal remains unknown
even with monitoring configured. No fake appraisal, licence validity or new
lending activation is part of pilot readiness. Production cutover and bulk
migration remain separate from the isolated operational rehearsal.
