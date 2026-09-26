---
status: accepted
owner: loans
updated: 2026-09-26
tags: [loans, origination, idempotency]
---

# One New loan form creates one draft

Repeated new-form POSTs previously allocated independent loan numbers. The owner
approved durable duplicate-submit protection and a visible saving state after
staff accidentally recorded several identical drafts within seconds.

## Decision

Each fresh New loan GET issues a signed random submission UUID bound to the
workspace and signed-in actor. Preview and validation errors retain that identity.
The HTTP create endpoint requires it; missing or invalid references fail closed
and direct the user to check Loans before opening a fresh form.

Store the UUID on the created PawnLoan. A partial unique constraint covers
`(workspace, creation_submission_id)` and a database trigger preserves the
identity and workspace and prevents hard deletion of a keyed loan. No new table,
cache, scheduled cleanup, payload fingerprint or duplicate time window is needed.
Existing and internal/import-created loans keep NULL; do not invent historical
submission identities. Loan creation services retain their existing internal
call contract with an optional submission ID.

The create command checks current authorization, locks the workspace row, checks
for completion, then creates the loan, allocates its number and attaches photos
in one transaction. A concurrent retry waits and returns the committed result.
Failed saves roll back the identity and number together and retain the existing
photo-compensation behavior. Workspace-level locking is intentionally simple;
storage latency can serialize other operations using that workspace lock.

A completed submission is recovered before revalidating stale choices or missing
re-uploaded files. It returns the original loan even if subsequently approved,
active or cancelled. Changed fields on a reused form are **not applied**; the
response explicitly says so and directs the user to Correct draft. Current
workspace access, actor binding, RLS and write permission still apply on replay.
The key does not expire independently of the loan: slow retries must not become
new loans. Signing-key rotation can invalidate old forms, which fail closed.

A fresh New loan form may create another genuinely identical loan. Do not infer
duplicates from borrower, amount, dates or photographs. Existing draft edits use
the loan ID and keep its number; this change does not introduce edit versioning.

The browser locks submission controls and displays Saving after price preflight
succeeds. Preserve the requested save/preview action in a hidden field because
disabled buttons are not submitted. Do not disable file inputs. Back navigation
restores controls without replacing the retained submission identity. Server
protection also applies with JavaScript disabled. There is no timed automatic
retry or automatic cancellation of existing loans.

## Verification and rollout

Cover simultaneous submissions, lost responses, changed payloads, cancelled
records, identical legitimate new forms, validation and photo failure retries,
actor/workspace restrictions, restricted-role constraint enforcement and repeated
draft edits. Browser tests cover price-check resumption, preview, keyboard submit,
pending controls and Back recovery.

Apply Loans 0027 with owner-only migration credentials; keep restricted runtime
credentials. Prepare static assets before briefly stopping old web writers and
activating the new code. Pre-upgrade open forms have no valid reference: staff
must check Loans and open a fresh New loan form. No existing duplicate record is
cancelled, deleted or renumbered by this rollout.
