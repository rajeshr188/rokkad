# Invitation Flow Reference

Date: 2026-03-28

## Purpose
This document explains the complete company invitation flow used in the SaaS workspace model:
- Platform signup is open.
- Company membership is invite-only.
- Invitation acceptance and membership creation are idempotent.

## Scope
This covers:
- Invitation creation
- Invitation acceptance
- Signal-driven membership assignment
- Pending invitation fallback for users who do not yet have an account
- Signup-time pending invitation consumption
- URL routing and endpoint behavior

Primary implementation files:
- apps/orgs/forms.py
- apps/orgs/models.py
- apps/orgs/views.py
- apps/orgs/signals.py
- apps/orgs/urls.py
- django_project/public_urls.py
- django_project/shared_urlpatterns.py
- django_project/settings/base.py

## High-Level Design
The invitation subsystem uses django-invitations with a custom invitation model:
- CompanyInvitation is the canonical invite record.
- Membership is the canonical company access record.
- PendingInvitation stores temporary invite intent when the invited email has no account yet.

Core rule:
- Membership grant source of truth is signal-driven logic in apps/orgs/signals.py, not view-level side effects.

## Data Models

### CompanyInvitation
Defined in apps/orgs/models.py.
Important properties:
- Foreign key to company
- Foreign key to role
- Email field
- unique_together on (email, company)
- create() helper and send_invitation() mail dispatch

### Membership
Defined in apps/orgs/models.py.
Important properties:
- Foreign key to user
- Foreign key to company
- Foreign key to role
- unique_together on (user, company)

This uniqueness guarantees one membership row per user-company pair.

### PendingInvitation
Defined in apps/orgs/models.py.
Important properties:
- Email
- Company
- Role
- Created timestamp
- unique_together on (email, company)

This model stores invites accepted before account creation and prevents duplicate pending records per company/email.

## URL Endpoints

### Included package URLs
- /invitations/accept-invite/<key>/ via include("invitations.urls")

Configured in:
- django_project/public_urls.py
- django_project/shared_urlpatterns.py

### Project team URLs
- /orgs/team/invitations/accept/<key>/
- /orgs/invitations/accept-invite/<key>/ (legacy)

Configured in apps/orgs/urls.py.

Current behavior:
- Both project-level accept endpoints route to AcceptInvite.as_view() to ensure consistent acceptance semantics.

## End-to-End Flow

### Flow A: Existing user receives invite and accepts
1. Inviter submits CompanyInvitationForm (apps/orgs/forms.py).
2. Form creates CompanyInvitation and sends email.
3. Invitee opens acceptance URL.
4. django-invitations AcceptInvite validates key and marks invite accepted.
5. invitations.signals.invite_accepted is emitted.
6. apps/orgs/signals.create_membership handles signal:
   - finds user by email__iexact
   - performs Membership.get_or_create(user, company, defaults={role})
7. User now has company membership.

Result: idempotent. Repeated accept callbacks do not create duplicate memberships.

### Flow B: Non-user accepts invite before signup
1. Invite created and email sent.
2. Invitee opens acceptance URL and invite is accepted.
3. invite_accepted signal fires.
4. Signal handler cannot find user by email.
5. PendingInvitation.get_or_create(email, company, defaults={role}) stores intent.
6. Later, invitee signs up through allauth.
7. allauth.account.signals.user_signed_up fires.
8. apps/orgs/signals.create_membership_on_signup:
   - loads all PendingInvitation rows for email__iexact
   - for each pending row, Membership.get_or_create(...)
   - deletes pending rows after processing (inside transaction.atomic)

Result: delayed membership assignment is deterministic and idempotent.

## Signal Contracts

### invitations.signals.invite_accepted
Source: django-invitations accept_invitation() in package views.
Signal payload used:
- email
- invitation
- request

Project receiver:
- apps/orgs/signals.create_membership

Responsibilities:
- Existing account path: grant membership idempotently.
- No account path: persist pending invite idempotently.

### allauth.account.signals.user_signed_up
Source: allauth account complete_signup() path.
Signal payload used:
- user
- request

Project receiver:
- apps/orgs/signals.create_membership_on_signup

Responsibilities:
- consume all pending invitations for signed-up email
- create memberships idempotently
- cleanup pending rows

## Idempotency and Safety Guarantees
1. Membership duplicates are prevented by:
   - DB constraint unique_together(user, company)
   - get_or_create in signal handlers

2. Pending invitation duplicates are prevented by:
   - DB constraint unique_together(email, company)
   - get_or_create for pending creation

3. Email matching normalization:
   - signal lookups use email__iexact

4. Multi-row pending consumption:
   - signup handler processes all pending rows for email, not only first()

5. Transactional cleanup:
   - signup consumption runs inside transaction.atomic

## Why View-Level Membership Creation Was Removed
A prior custom accept wrapper created Membership directly in the accept view.
That approach had risks:
- duplication with signal logic
- possible pre-validation side effects
- race conditions and IntegrityError risk

Current design keeps membership creation in signals as single source of truth.

## Operational Notes
- Signal registration is loaded through apps.orgs.apps.OrgsConfig.ready().
- Keep AppConfig enabled in INSTALLED_APPS so receivers are connected.
- If invitation behavior appears broken, verify signal registration first.

## Testing Coverage Guidance
Current tests should verify:
- existing user invite acceptance creates membership once
- unknown user acceptance creates pending invitation
- signup consumes all pending invitations
- noop behavior for malformed signal payloads

Recommended additional integration tests:
- repeated accept URL hits on same key
- concurrent signal delivery simulation
- case-variant email invitation and signup
- legacy and new accept URLs produce equivalent outcomes

## Troubleshooting Checklist
1. Membership not created after accept:
   - check invitation accepted status
   - check invite_accepted receiver wired
   - check email case and user existence

2. Membership not created after signup:
   - check PendingInvitation row exists
   - check user_signed_up receiver wired
   - check handler processed all rows and deleted pending

3. Duplicate membership errors:
   - verify no manual Membership.create in views
   - verify signal handler uses get_or_create

4. Inconsistent endpoint behavior:
   - verify both accept URLs route to AcceptInvite.as_view()

## Change History Snapshot
- Signal handlers hardened for idempotency and case-insensitive lookup.
- Custom accept view side effects removed.
- PendingInvitation uniqueness added.
- Accept endpoints unified to base AcceptInvite flow.
