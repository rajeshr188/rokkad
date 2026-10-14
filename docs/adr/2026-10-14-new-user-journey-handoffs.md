---
status: accepted
owner: project
updated: 2026-10-14
tags: [onboarding, authentication, workspace, ux]
related: [2026-10-10-guided-business-setup.md, 2026-10-10-initial-setup-before-activation.md, 2026-09-29-selected-public-trial.md]
---

# Preserve the existing lifecycle while connecting new-user handoffs

The owner approved implementing the [new-user audit](../implementation/new-user-journey-audit-20261014.md)
recommendations with regression protection. The current six-step presentation,
loan services and explicit commercial activation remain authoritative.

Use allauth's supported `ACCOUNT_LOGIN_METHODS` with email and username, preserving
existing usernames, account IDs, authentication backends, password checks,
verification/invitation gates and rate limits. Do not require account migration
or remove the signup username in this increment. The pinned runtime contract is
django-allauth 65.19.4; deployment dependency validation remains separate.

The exact global `/contact/` page serves public support. The retired Contact
bookmark adapter must not shadow it. Neighboring legacy URLs, mapped Workspace
domains, membership checks and explicit Workspace context remain unchanged; a
tenant Contact bookmark still redirects to Party. No broad public-prefix exception.

Verification may remember only the account ID and a currently owned active
Workspace ID after an explicit resend request. Revalidate current ownership,
active lifecycle and membership before constructing a canonical setup return.
No arbitrary URL, token, authority or business-completion state is stored.
Different-device confirmation falls back to a validated owned navigation
preference. Anonymous confirmation returns through signin; target pages retain
their normal authorization/RLS checks. Invitation and explicit safe allauth next
destinations retain precedence. Mail intents/providers remain unchanged.

Trial activation still requires verified canonical email, current owner consent,
the selected offer, allowance and capacity/history checks. Fixed guided step/path
markers return to the already-resolved Workspace; failure retains those markers.
Without markers, preserve the existing legacy team-onboarding continuation or
return a newly activated business to derived setup. No automatic trial starts,
paid consent, access grants or new activity mode.

Lending readiness and monitoring-policy readiness are separate derived outputs.
Resolve today's applicable monitoring policy for each running series's licence,
with the existing workspace-default/licence-override resolver. Do not change the
six lending checks, create policies on reads, infer risk completeness from a policy
or weaken origination. Financial/collateral evidence and saved assessment freshness
remain separate requirements. Owners choose and save workflows/policies explicitly
through existing commands. Existing loan terms and completed actions are unchanged.

Focused navigation is presentation within guided setup only; the full authorized
menu remains available. Normal counter screens stay unchanged. Optional worked
examples remain read-only and do not replace real loan review. No model, migration,
wizard framework or new financial workflow is required.
