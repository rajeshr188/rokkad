---
status: active
owner: project
updated: 2026-09-29
tags: [deployment, trial, onboarding, operations]
related: [../plans/public-workspace-trial.md, platform-mail.md, ../adr/2026-09-29-owner-public-trial-allowance.md]
---

# Public trial production release, 29 September 2026

The 30-day free offer is enabled and verified at **19:07 IST**. It includes owner
plus five staff, one trial Workspace per owner account, verified-owner consent,
no card and no automatic charge. Existing Workspaces retain their accepted dates
and access. Paid continuation requires a separate launch and explicit consent.

## Deployed source and configuration

Web, dispatch, feedback, recovery and health use `rokkad:public-trial-20260929-e06bb85c285c`
(`sha256:bdc850b3f6fcac64ec39216d09b2b7ce2e694e3f4d05a9fe7c38634caa370afe`).
Source is the reviewed subset of `61be6f93`: onboarding routing, org control-plane
seat locks, subscription billing/services/views/public_trial/catalog command,
three subscription templates and login/signup templates, plus the targeted
selected-plan setting in base settings. Thirteen deployed file hashes were checked.
The overlay preserves the previous app outside those files and the current static
volume. No migration or dependency change. Runtime remains restricted, with 117
forced-RLS tables. Permanent admin user 9 and disabled test user 11 are unchanged.

| Setting | Current value |
| --- | --- |
| `BILLING_PUBLIC_TRIAL_PLAN_ID` | `3` |
| `BILLING_ALLOW_TRIAL_START` | `True` |
| `BILLING_CHECKOUT_ENABLED` | `False` |
| `BILLING_RECURRING_ENABLED` | `False` |
| `BILLING_PROVIDER_MODE` | `live`, configuration only |
| `ACCOUNT_EMAIL_ENABLED` / `PLATFORM_EMAIL_ENABLED` | Both `True` |

The trial flag is set consistently in Compose and the public/private worker
environment files. The shared `production_settings.py` explicitly overrides the
inherited hard-false production default with:

```python
BILLING_ALLOW_TRIAL_START = env.bool("BILLING_ALLOW_TRIAL_START", default=False)
```

Preserve that reviewed override in future deployment settings. The first attempt
without it rolled back because effective web/worker flags remained false. Candidate
settings must retain the original file's read permissions for the non-root container;
private credentials remain root-only. No secret values changed. Web still has no
SES credentials; signing/token settings match across web and worker.

## Verification

A fresh operational database backup was hash/catalog verified. Candidate checks
confirmed exact Plan 3 terms and excluded private Plans 1/2. Deployment initially
kept trials off. A restricted-runtime acceptance transaction then created fictional
non-admin rows, exercised the real trial/member services and rendered the offer:
unverified owner and private/stale terms refused, 30-day nonrenewing trial accepted,
six-person capacity enforced, repeat/second-Workspace starts refused, correct
consumed-allowance copy, and full/grace/read-only dates verified. The entire
transaction rolled back; no persistent user, Workspace, trial, financial or mail
record remained. Database sequences may advance during rolled-back checks.

This is a service/render acceptance check, alongside the prior isolated browser
journey and real email/link acceptance. No new real signup, invitation or email
was submitted. The earlier 51 focused trial/catalog/billing/access tests remain
the source regression evidence; this release changes no application source beyond
that reviewed set.

After activation, HTTPS login and signup returned 200 with their forms and current
copy. All four mail timers are active/enabled. Supervised workers, the next natural
scheduled run and health passed; queue due is zero and there are no health flags.
Mail remains `--send --limit 10 --invitations-and-accounts`, excluding receipts.
All observed subscription/mail/Company/Membership/invitation fingerprints and
existing Workspace access/trial dates match the release baseline. Existing Plan 1
and private Plan 2 were not changed or assigned by this release.

## Recovery and follow-up

To pause new free trials, set the trial flag false consistently in Compose and
both worker environment files, recreate web and verify effective settings. Preserve
the selected plan, existing acceptance events, subscriptions and mail flags.
Pausing new starts does not revoke already accepted trials. Never restore an older
generic-catalog image with trial signup enabled: it lacks selected-plan isolation
and owner allowance checks. Prefer pausing the flag while retaining this image.

Private backups, source manifests and checks are under
`/home/rokkad/deploy/cutover-20260924/public-trial-release-20260929/`, including
`prepared.json`, `applied.json`, `verified.json`, `acceptance.json`, `activated.json`
and `active-verified.json`. Local sanitized reports are
`outputs/public-trial-release-*-20260929.json` and
`outputs/public-trial-runtime-acceptance-20260929.json`.

Monitor the first genuine owner signup, trial acceptance and team invitation
through ordinary operations. The supported billing inbox is already established;
paid continuation remains unavailable pending the
[monthly pilot gates](../plans/monthly-billing-pilot.md). Do not infer a charge,
recurring mandate or paid launch from free-trial activation.
