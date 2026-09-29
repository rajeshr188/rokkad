---
status: accepted
owner: project
updated: 2026-09-29
tags: [identity, email, security]
related: [2026-09-26-durable-platform-mail.md, ../implementation/platform-mail.md]
---

# Durable account verification and password-reset email

Production's shared Django backend is locmem, while the dedicated SES invitation
worker is operational. Public password signup needs delivered verification mail;
account recovery needs reset mail. Giving the web process SES credentials or
switching every legacy email path is unnecessary.

Extend the existing platform-mail outbox with a global `AccountEmail` source for
verification and password-reset intents. Each Delivery references exactly one
invitation, paid invoice or account intent. Account intents belong to global user
identity, have no Workspace content, expose no general CRUD or Workspace retry
route, and have no default model permissions. They are control-plane operational
records, not Workspace-owned data requiring RLS. Restricted runtime roles remain
mandatory. User deletion is protected by retained intent evidence; deleting an
EmailAddress clears its relation and invalidates the queued fingerprint.

An allauth adapter overrides only confirmation and reset-mail hooks, retaining
the existing invitation signup policy and library views, rate limits and token
validation. The invitations package's historical adapter exists only when its
old class name is configured, so the new adapter extends DefaultAccountAdapter
and delegates signup policy to BaseInvitationsAdapter. Both adapter settings use
the new class. `ACCOUNT_EMAIL_ENABLED=False` retains the previous mail hooks.
Unknown-account and other security notifications retain the shared backend;
this decision does not claim those paths deliver through SES.

Queue source references, recipient and a keyed fingerprint of account state;
never store token-bearing bodies, request-host URLs, passwords or raw state in
the outbox. Lock the user to coalesce pending/sending/uncertain duplicate requests.
Intents expire after at most 30 minutes (or the shorter password-reset timeout).
Before dispatch, reject expired, inactive, changed or no-longer-needed sources
and suppressed recipients. Reset fingerprints include password and last login;
verification deliberately permits the signup login that happens after enqueue.

Generate native allauth HMAC verification/reset links only while rendering for
dispatch against the configured canonical HTTPS origin. Link validity begins at
rendering and follows allauth/Django expiry settings; the 30-minute bound is the
queue intent lifetime, not a replacement token lifetime. Code-based flows are
unsupported and fail closed. Web and worker must share signing secrets and token
configuration; validate that privately before activation or pending intents will
fail fingerprint checks and links will be invalid.

Delivery attempts, SES correlation, bounce/complaint suppression, bounded definite
throttle retries and conservative uncertain-outcome handling reuse the existing
worker. Workspace retry refuses account mail; request a new email through the
rate-limited account flow. No automatic replay of an uncertain attempt is added.

`--accounts-only` and `--invitations-and-accounts` allow bounded account dispatch;
the latter excludes all receipts before applying the batch limit. Existing
invitation-only scheduling does not acquire account messages automatically.
Actual account dispatch requires both mail enablement flags. Captures do not send.

Roll out schema and matching web/worker code with account sending paused, verify
runtime grants and configuration alignment, then accept specifically authorized
real verification/reset messages before advertising password-based public trials.
No public trial or charging flag changes as part of this decision.

The integration points follow the installed allauth implementation and its
[adapter documentation](https://docs.allauth.org/en/dev/account/adapter.html).
