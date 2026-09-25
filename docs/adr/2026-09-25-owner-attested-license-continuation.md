---
status: accepted
owner: project
updated: 2026-09-25
tags: [loans, licensing, migration, evidence]
---

# Continue an imported licence while its document is pending

The owner explicitly approved deferring the original licence documents during
production cutover, while confirming the four existing licence identities and
expiry on January 10, 2030. The supplied GST certificate is not substituted as
licence evidence. This supersedes the mandatory-document prerequisite in the
[September 22 continuation decision](2026-09-22-verified-legacy-license-continuation.md)
only for an explicit Workspace-owner attestation.

The existing continuation service accepts an optional `document_deferral_reason`.
Only the canonical Workspace owner may use it; setup permissions, lifecycle,
source completeness, numbering review and all existing guards still apply.
Document deferral requires a nonempty bounded reason and rejects any substitute
file. It appends kind `ATTESTATION`, labelled "Owner attestation (document pending)",
with the actor, owner-declared validity and unchanged source/numbering evidence.
It does not claim government or document verification. Ordinary `VERIFICATION`
continues to require the document and its hash. Database triggers distinguish the
two kinds and reject incomplete evidence or direct activation.

The licence and series identities, existing number reservations, immutable source
revisions and old loans' frozen revision references survive unchanged. New lending
uses the attested revision and normal product/policy/approval checks. The licence
register and detail page clearly show the pending document, with a link to upload
it through the existing Edit/amendment workflow. That upload appends evidence;
it never rewrites the original attestation or the imported loan history.

This is an operator service path, not a new general self-service verification form.
Migration `0018_owner_attested_continuation` is forward-only and does not activate
any row by itself. No RLS, numbering, loan-state or financial posting guard is
disabled. For this cutover, valid-from is the continuation date because the owner
attests current validity; it is not a claim about the original issue date. The
original dates can be recorded later through an amendment with the proper document.

