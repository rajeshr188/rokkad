---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Django-Allauth Enhancements Backlog

Date: 2026-03-28

## Purpose
Track optional allauth improvements after baseline hardening is complete.

## Planned Enhancements

### 1) Email-only signup
- Remove username requirement from signup UX.
- Suggested settings:
  - `ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]`
  - `ACCOUNT_LOGIN_METHOD = {"email"}`
- Notes:
  - Confirm downstream code does not rely on `username`.
  - Consider default username generation only if legacy dependencies require it.

### 2) Stronger email verification policy
- Current: `ACCOUNT_EMAIL_VERIFICATION = "optional"`
- Future target: `"mandatory"` for stricter account trust.
- Rollout guidance:
  - Enable in staging first.
  - Validate invite and social-login flows are not blocked unexpectedly.

### 3) MFA for high-privilege users
- Evaluate `allauth.mfa` (TOTP).
- Scope:
  - Require MFA for workspace roles: Owner/Admin.
  - Keep Member MFA optional initially.
- Dependencies:
  - Verify installed allauth version supports MFA flow used.

### 4) Social signup invite-linking hardening
- Ensure Google signup consistently resolves pending invitations by email.
- Keep membership creation idempotent in signals.
- Add regression tests for:
  - invite accepted before signup
  - signup before invite accepted
  - repeated callback/signal delivery

### 5) Optional adapter customization (only if needed)
- No custom AccountAdapter is required for current policy (open platform signup + invite-only company membership).
- Add a custom adapter only for UX/flow refinements, such as:
  - custom post-signup routing logic
  - conditional messaging
  - provider-specific signup behavior

## Suggested Implementation Order
1. Email-only signup
2. Invite-linking test hardening
3. MFA rollout
4. Mandatory verification decision
5. Adapter customization (if still needed)

## Exit Criteria
- Signup/login/social flows pass functional tests.
- Invitation-to-membership path remains idempotent.
- No increase in support incidents related to auth onboarding.

