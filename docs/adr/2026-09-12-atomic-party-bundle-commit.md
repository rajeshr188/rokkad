---
status: accepted
owner: project
updated: 2026-09-12
tags: [adr, portability, approval, transaction]
---

# Dependency-aware Party bundle review and atomic commit

The owner authorized the next slice after
[bundle staging](2026-09-12-party-bundle-staging.md). A combined review page consumes
the existing signed staging receipt. It accepts explicit destination role mappings,
shows all normalized rows/dispositions/issues in dependency order, and offers one
approval for the nonempty profiles. Individual batch workflows remain available.
No new model, migration, dependency or business schema is introduced.

## One execution path for preview and commit

Existing child validators resolve real Party identities and invoke native forms.
Rather than introduce a second in-memory Party model/validator, evaluate the existing
validate/commit services in master/contact/address/identifier/role/relationship order
inside a savepoint. A preview always rolls that savepoint back. It retains only a
plain-data result and signed approval. New parents exist transactionally for child
validation, without becoming visible outside the transaction or being retained.
If a profile has errors, stop dependency evaluation and issue no approval.

All current services in this path write database state only. There are no Party
post-save receivers that send external effects. Audits, source identities, native
Party code allocation, batch revisions and completion evidence roll back with the
savepoint; on_commit callbacks are discarded. PostgreSQL surrogate-ID sequences
can advance despite rollback, leaving ordinary internal-ID gaps. Do not show those
simulated IDs/local Party codes as confirmed results. Future inline emails, files,
provider calls or other nontransactional effects in this path require redesign;
transaction.on_commit is the supported boundary for deferred external effects.
This decision does not extend simulated writes to Loans or accounting workflows.

Confirmation repeats the exact execution path inside one outer atomic transaction,
then compares the evaluated plan digest before it can commit. Constraint checks run
explicitly before preview rollback and real completion, including deferred SQL
integrity checks. Any error/difference rolls back every profile, including audit
and identity writes. Native uniqueness, primary-contact effects, role history and
relationship rules remain in the existing commands. Company serialization, ordered
batch/row locks and native destination locks remain held through confirmation.

## Approval and replay

The existing receipt binds the exact six-profile membership and destination
Workspace, expires after one day and is accepted only after current import access
checks. Empty profiles need no batch; all-empty bundles have nothing to commit.
Combined review requires every nonempty batch to be unfinished. An individually
completed/cancelled profile prevents combined commit of the rest; use the existing
individual workflow instead. The operation never rewinds a prior committed profile.

A dedicated signed approval expires after one hour and binds Workspace, operator,
receipt, role mapping, staged input digest and evaluated plan digest. Input includes
batch IDs, state/revision/mapping/approval/source evidence and all staged row values.
The plan includes normalized canonical values, dispositions, issues and summaries.
Keep destination role definition snapshots in the plan. Omit only the generated
relationship _parties database binding: both portable endpoint references remain,
and existing immutable source identity resolution/native validation enforce them.
New surrogate parent IDs necessarily differ after simulated inserts roll back.

Confirmation requires the acknowledgement checkbox and rechecks import plus Party
create/edit permissions before writes and before replay. It rejects expired,
foreign-Workspace/operator, altered or stale approvals. Revalidation, cancellation,
individual commit, source changes, destination conflicts or changed role definitions
require a new combined review. Staged rows are not silently rewritten for approval.

Before each real profile completion, retain the combined approval hash in that
batch's summary. Existing PostgreSQL completed-row immutability protects it. All
profiles with the same hash completed means replay returns existing results without
writing again, but only after current permission checks. A successful aggregate
audit links the hash and batch UUIDs; ordinary per-profile audits remain. The marker
is omitted from the product's individual summary display. No private row values
are copied to aggregate audit fields. A failed aggregate adds no completion audit.

## Operator limits and future work

Use **Review and commit whole bundle** on the staging results page, map role types,
generate the combined preview, inspect each profile/row and confirm once. The page
uses normal Workspace middleware, CSRF protection and no-store responses; it has no
commercial or lifecycle exemption. The original synchronous upload/row/byte limits
remain. Preview temporarily holds database locks and costs roughly the import work;
it is not background execution or production capacity acceptance.

The receipt remains valid for one day. After expiry, individual batches remain
available in Recent imports, but the combined group is not independently stored.
The then-recommended persistent history follow-up is now implemented in the
[history decision](2026-09-12-persistent-party-bundle-history.md). The preceding
receipt-only limitation describes this earlier checkpoint. Preset transfer/deletion, full
Workspace archives, KYC binaries and Loans remain deferred. Loans restoration and
opening-position semantics still require separate domain and executable contracts.
