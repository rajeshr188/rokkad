---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

Iâ€™ll trace the full invite lifecycle in code (models, signal registration, invitation acceptance flow) and then give you a concrete edge-case review with fixes/tests prioritized by risk.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/models.py#120-120), lines 120 to 230

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/views.py#1-1), lines 1 to 220

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/apps.py)

Iâ€™ve confirmed signals are loaded via `OrgsConfig.ready()`. Next Iâ€™ll inspect the invite accept path and where each signal fires so the behavior is exact, not hypothetical.

Searched for regex `invite_accepted|AcceptInvite|CompanyInvitation|PendingInvitation|invitations` (`**/apps/**/*.py`), 20 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/.venv314/Lib/site-packages/allauth/account/signals.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/.venv314/Lib/site-packages/invitations/signals.py)

Searched for regex `class .*AcceptInvite|AcceptInvite\(` (`**/apps/**/*.py`), 1 result

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/views.py#260-260), lines 260 to 380

Searched for regex `CustomAcceptInvite|accept-invite|invitations/accept|confirm-invitation|invitations.urls|invitations` (`**/*.py`), 20 results

Searched for regex `CustomAcceptInvite|AcceptInvite|workspace_invitations|companyinvitations_list|team_invite` (`**/apps/orgs/urls.py`), 8 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/urls.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/forms.py#1-1), lines 1 to 230

Searched for text `user_signed_up.send` (`**/.venv314/Lib/site-packages/allauth/**/*.py`), no results

Searched for text `invite_accepted.send` (`**/.venv314/Lib/site-packages/invitations/**/*.py`), no results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/.venv314/Lib/site-packages/invitations/views.py)

Searched for text `user_signed_up.send` (`**/*.py`), 1 result

Searched for text `invite_accepted.send` (`**/*.py`), 1 result

Searched for regex `ACCEPT_INVITE_AFTER_SIGNUP|CONFIRM_INVITE_ON_GET` (`**/django_project/settings/*.py`), no results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/.venv314/Lib/site-packages/allauth/account/utils.py#170-170), lines 170 to 230

I found where both signals are emitted in third-party code; next Iâ€™ll verify invitation settings defaults so we can reason about your exact runtime flow.

Searched for regex `INVITATIONS_CONFIRM_INVITE_ON_GET|INVITATIONS_ACCEPT_INVITE_AFTER_SIGNUP|INVITATIONS_SIGNUP_REDIRECT` (`**/django_project/settings/*.py`), no results

Searched for regex `unique_together = \("email", "company"\)|unique_together = \("user", "company"\)` (`**/apps/orgs/models.py`), 3 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/.venv314/Lib/site-packages/invitations/app_settings.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/.venv314/Lib/site-packages/invitations/urls.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/onboarding/views.py#230-230), lines 230 to 320

Searched for regex `def accept_invitation|def post\(self, \*args, \*\*kwargs\):|def complete_signup|class CustomAcceptInvite|Membership.objects.create\(|PendingInvitation.objects.filter\(email=email\)` (`**/*.py`), 15 results

Searched for regex `class PendingInvitation|class Membership|unique_together = \("user", "company"\)|unique_together = \("email", "company"\)` (`**/apps/orgs/models.py`), 5 results

Searched for regex `ACCOUNT_ADAPTER|INVITATIONS_ADAPTER|INVITATIONS_INVITATION_MODEL|ACCOUNT_SIGNUP_FIELDS` (`**/django_project/settings/base.py`), 4 results

Searched for regex `invitations/|team/invitations/accept|invitations/accept-invite` (`**/django_project/*.py|apps/orgs/urls.py`), no results

Searched for regex `include\("invitations.urls"\)|include\("allauth.urls"\)` (`**/django_project/public_urls.py`), 2 results

Searched for regex `include\("invitations.urls"\)|include\("allauth.urls"\)` (`**/django_project/shared_urlpatterns.py`), 2 results

Searched for regex `team/invitations/accept|invitations/accept-invite` (`**/apps/orgs/urls.py`), 2 results

**Findings (Focused Review, Highest Risk First)**

1. Critical: invitation replay can grant membership before validity checks  
The custom accept view creates membership before checking whether invite is expired/already accepted.  
- Code: views.py, membership create at views.py  
- Why risky: a previously accepted link can still trigger membership creation before parent logic rejects it.

2. High: duplicate membership creation path (double-write race)  
Both custom accept view and invite_accepted signal try to create membership for existing users.  
- Custom create: views.py  
- Signal create: signals.py  
- Unique constraint: models.py  
- Result: IntegrityError risk or flaky behavior on repeated acceptance requests.

3. High: pending invite handling is not idempotent  
Pending invites are created with plain create and no uniqueness, then signup consumes only first row.  
- Pending create: signals.py  
- Pending lookup first(): signals.py  
- Pending model starts: models.py  
- Risk: stale pending rows, repeated/ambiguous membership assignment.

4. Medium: email lookup on invite_accepted is exact-match, not normalized/case-insensitive  
- Exact lookup: signals.py  
- Risk: existing user with case-variant email can be treated as not found, producing wrong PendingInvitation behavior.

5. Medium: two acceptance endpoints can diverge behavior  
You include package invitations URLs and also custom accept URLs.  
- Package include: public_urls.py, shared_urlpatterns.py  
- Custom accept endpoints: urls.py, urls.py  
- Risk: inconsistent flow depending which URL is hit (email link vs internal links).

6. Low/operational: signal handlers have print debugging and no transactional guard  
- Prints and direct writes: signals.py  
- Risk: noisy logs and partial state in error scenarios.

---

**How user_signed_up and invite_accepted Actually Work**

1. allauth user_signed_up  
- Defined in allauth/account/signals.py  
- Emitted during signup completion in utils.py via send at utils.py  
- Meaning: fires when a new account is successfully created (not on regular login).

2. invitations invite_accepted  
- Emitted when invitation is marked accepted in views.py, send at views.py  
- Default package behavior with your settings: ACCEPT_INVITE_AFTER_SIGNUP defaults False in invitations/app_settings.py, so invite is accepted first, then user is redirected to signup.

3. Your appâ€™s combined flow today  
- invite_accepted receiver: if user exists, create membership; else create PendingInvitation in signals.py  
- user_signed_up receiver: consume PendingInvitation and create membership in signals.py  
- This is exactly the right pattern for open signup + invite-only company membership, but implementation needs hardening on idempotency and endpoint consistency.

---

**Do you need a custom AccountAdapter for this?**

No, not for your policy goal.

Your policy is:
- Open account signup platform-wide
- Invite-only membership per company

That can be fully enforced at membership/invitation layer (which you already do) without a custom AccountAdapter. Adapter customization is optional for refinements, not required for core policy.

---

**Recommended Hardening (No Product Policy Change)**

1. Make membership writes idempotent  
Use get_or_create for membership creation in both signal handlers and remove duplicate creation from custom accept view.

2. Remove or neutralize CustomAcceptInvite membership side effect  
Let invite acceptance signal be single source of membership grant.

3. Add uniqueness for pending invites  
Unique on email+company+role (or email+company) and use get_or_create in signal.

4. Normalize email comparisons  
Use iexact or normalized email pipeline in signal lookups.

5. Add regression tests for edge cases  
- Existing user accepts invite once  
- Existing user re-opens same invite link  
- Non-user accepts invite then signs up  
- Duplicate invite_accepted signal delivery  
- Concurrent accept requests for same invite key

If you want, I can next do a line-by-line remediation plan for signals.py and views.py with exact safe logic before you implement.
