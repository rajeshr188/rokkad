---
status: future
owner: notify-v2
updated: 2026-08-13
tags: [notify-v2, whatsapp, tenancy, readiness, acceptance]
related:
  - ../adr/2026-08-13-workspace-owned-whatsapp-cloud-integrations.md
  - ../adr/2026-08-14-whatsapp-cloud-api-only.md
  - ../implementation/whatsapp-notifications-architecture-audit.md
---

# Workspace WhatsApp Cloud integration acceptance

## Goal

Give each Workspace Owner/Admin a controlled way to prove that the workspace's
saved Meta integration can send and receive authenticated evidence. Saving or
enabling credentials alone must not mean operational readiness.

## Scope

Add an explicit **Test integration** workflow to the existing workspace
WhatsApp setup page:

1. Re-read and decrypt the active workspace integration.
2. Ask Meta for the configured phone-number identity using the saved token.
3. Require the returned phone-number ID to equal the saved workspace value.
4. Show the tenant-specific HTTPS callback URL and webhook verification state.
5. Require an active Notify WhatsApp template carrying an approved Meta template
   name and language.
6. Let Owner/Admin select an explicit test recipient and preview the exact
   approved template payload.
7. Require confirmation before creating one test event/job.
8. Submit through the ordinary Notify v2 WhatsApp dispatch boundary.
9. Wait for an HMAC-authenticated, phone-ID-matched Meta callback.
10. Mark the test accepted only after the same provider message ID reaches
    authenticated `delivered` or `read` evidence.

The test must not create a PawnLoan notice, resolve a risk alert, contact a
borrower implicitly, or enable automatic communication.

## State and evidence

Keep acceptance evidence separate from mutable credentials. Add the smallest
tenant-scoped test-run record containing:

- workspace integration identity and non-secret configuration version;
- initiating actor and timestamps;
- selected test recipient snapshot;
- template ID, version, Meta name, language, and frozen provider payload;
- linked Notify event/job and provider message ID;
- submission result and sanitized provider diagnostic;
- matched authenticated receipt and final status;
- accepted/failed/expired outcome.

Editing the phone-number ID, access token, app secret, API version, or enabled
state invalidates prior readiness. Historical test evidence remains immutable.
Secret values and authorization headers must never enter the database evidence,
logs, messages, templates, or error pages.

## Readiness rules

The workspace is operationally ready only when all are true:

- the tenant integration exists and is enabled;
- the deployment encryption key can decrypt every required secret;
- Meta authentication succeeds;
- Meta confirms the configured phone-number identity;
- the tenant callback has passed verification;
- a controlled template test was submitted successfully;
- an authenticated callback for that exact provider message reached
  `delivered` or `read`;
- no credential or identity change occurred after the accepted test.

The existing readiness command and UI must report each blocker individually.
Network failures remain retryable failures; they must never be treated as
successful acceptance.

## Permissions and tenant isolation

- Owner/Admin/platform admin may run the test.
- Members may see only the resulting ready/blocked status if their existing
  Notify permissions allow it.
- Every lookup begins from the active tenant integration.
- Cross-workspace integration, template, job, receipt, and test-run identifiers
  fail tenant-safe.
- The callback continues to select the tenant by hostname before decrypting or
  validating credentials.

## KISS workflow

Use ordinary Django forms, server-rendered responses, and the existing Notify
dispatch and receipt services. Do not add a provider abstraction, background
workflow engine, polling framework, automatic retries, or PawnLoan-specific
test path. A normal page refresh may display callback progress in v1.

## Test plan

- Owner/Admin access succeeds; Member mutation is forbidden.
- Secrets remain encrypted and absent from responses, logs, and evidence.
- Meta authentication and phone-ID mismatch fail closed.
- Disabled, missing, undecryptable, or changed integration fails closed.
- Missing/unapproved template and invalid recipient block before job creation.
- Double confirmation creates one test event/job.
- Unsigned, wrong-secret, wrong-tenant, and wrong-phone callbacks are rejected.
- Replayed callbacks do not duplicate evidence or transitions.
- Only a matching authenticated `delivered` or `read` receipt grants acceptance.
- Credential or identity edits invalidate readiness without deleting history.
- `check_whatsapp_cloud_readiness --fail-on-blocker` reflects the accepted test.
- Tenant migration replay, Django checks, focused tests, and migration drift pass.

## Explicitly deferred

- Automatic PawnLoan borrower communication.
- Channel fallback.
- Bulk messaging.
- Free-text WhatsApp messages.
- Automatic template creation or Meta business onboarding.
- Embedded OAuth/business-login onboarding.
- Master-key rotation tooling.

## Decisions to confirm when work resumes

1. Must the test recipient be the workspace owner's verified number, or may an
   Owner/Admin enter any consented test number?
2. Should acceptance expire after a fixed period, or only after integration
   configuration changes?
3. Is `delivered` sufficient, or should production acceptance require `read`?
4. Should the setup page call Meta synchronously in v1, or queue the identity
   check through an existing worker deployment?
5. May Admin accept an integration, or should final acceptance require Owner?

## Restart point

When implementation resumes, first answer the five decisions above. Then add an
ADR only if those answers change the accepted workspace-ownership boundary.
Implement identity verification and immutable test evidence before adding the
send-test button.
