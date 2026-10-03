---
status: accepted-local
owner: project
updated: 2026-10-03
tags: [khata, labels, custody, rls]
---

# Selected Khata collateral label batches

Phase 8 of the agreed improvement sequence removes the all-held selection barrier
for large accounts. Keep each issue bounded to 100 items; offer a searchable
100-item picker and one label per explicitly selected item. Print-displayed-batch
submits the identities staff saw, rather than recomputing a moving page at POST.
New searches/pages start a fresh selection. The server never silently adds later
receipts or substitutes another item for a returned selection.

Extend `khata-label/1` with mode `SELECTED`, preserving the existing three modes,
request hashes and retained PDF bytes. Save membership and ascending item-number
order in the immutable issue payload. The existing renderer emits one 100 x 60 mm
page and private item-UUID QR per selected item, preserving the 6 pt floor and
complete-text overflow refusal. No new model, job or financial source is needed.

Normalize selection order before request hashing; duplicates, invalid identities
and more than 100 items are refused. Exact retries retrieve the saved issue before
checking today's custody, including after actual handover. A new issue must find
every selected identity physically held in the same account and Workspace. Pending
returns remain physically held and carry their distinct custody caption.

Migration `0042_khata_label_batches` extends the existing database guard to selected
subsets and canonical order; `ALL`/`EACH` still require the complete holding. It
branches from the verified Khata series migration. The full-checkout no-op merge
`0050_merge_khata_label_batches` also joins the independent ordinary-loan branch;
that merge and ordinary branch are excluded from the composed Khata pilot image.
No existing forced RLS, immutable-document or identity/custody guard is weakened.

Native recovery retains fourteen tables but has a changed schema/guard fingerprint.
Restore older native archives with their matching image/schema, then migrate
forward; do not relax the mismatch gate. Full database/private-media backups and
the prior local image remain the rollback evidence. Printing and scanning on real
hardware remain separate acceptance requirements. Production is outside this slice.
