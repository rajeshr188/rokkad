---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

Search complete: Find all allauth usage in project

Searched for regex `allauth|ACCOUNT_|SOCIALACCOUNT_`, 200 results

Searched for files matching `**/templates/account/**`, 14 matches

Searched for files matching `**/templates/socialaccount/**`, no matches

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/accounts/views.py#1-1), lines 1 to 60

Searched for files matching `**/templates/account/*`, 12 matches

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/accounts/forms.py#1-1), lines 1 to 60

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/orgs/signals.py#1-1), lines 1 to 50

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/accounts/models.py#1-1), lines 1 to 50

Now I have a complete picture. Here's the full assessment:

---

## django-allauth Usage Review

### What you're using

| Feature | Status | Notes |
|---|---|---|
| `allauth.account` | âœ… Active | Email+username login, signup, logout |
| `allauth.socialaccount` + Google | âœ… Active | OAuth2/PKCE, profile picture sync |
| Custom templates | âœ… Partial | login, logout, signup, password reset/change/set overridden |
| `social_account_added` / `updated` signals | âœ… Active | Saves Google profile picture to `UserProfile` |
| `invite_accepted` signal (django-invitations) | âœ… Active | Creates `Membership` on accept |
| `ACCOUNT_ADAPTER` | âœ… Set | `InvitationsAdapter` â€” allauth adapter delegates to invitations |
| `INVITATIONS_INVITATION_MODEL` | âœ… Set | `orgs.CompanyInvitation` |
| Management command `fetch_google_profile_pics` | âœ… Exists | Backfill for existing users |

---

### What's broken / misconfigured

| Issue | Location | Fix |
|---|---|---|
| **Hardcoded Google client_id in templates** (`data-client_id="123-secret..."`) | login.html, signup.html | Use `{{ GOOGLE_CLIENT_ID }}` from settings via a context processor |
| **`ACCOUNT_SIGNUP_FIELDS` typo** â€” missing comma between `"username*"` and `"password1*"` | settings/base.py | `["email*", "username*", "password1*"]` |
| **`user_signed_up` signal is commented out** in signals.py | signals.py | Pending invitation â†’ membership flow is incomplete; users who sign up after accepting invite never get their membership created |
| **`allauth.urls` included twice** in both `public_urls.py` and `shared_urlpatterns.py` | public_urls.py, shared_urlpatterns.py | Likely causes duplicate URL names; one of them should be canonical |

---

### What you're not using (but would benefit from)

**High value for this project:**

1. **Email verification** (`ACCOUNT_EMAIL_VERIFICATION = "mandatory"`)  
   Currently unset. In a multi-tenant SaaS with billing, unverified emails are a risk. Allauth can mandate verification before workspace access is granted.

2. **Custom `AccountAdapter`**  
   You have `InvitationsAdapter` but no project-specific adapter. A custom adapter overriding `is_open_for_signup()` would let you gate signups to invited users only â€” critical for a private SaaS.

3. **`user_signed_up` signal** (currently commented out)  
   The `PendingInvitation` â†’ `Membership` flow on post-signup is partially written but disabled. This is a real gap: if someone accepts an invite before they have an account, their membership is never created.

4. **`ACCOUNT_USERNAME_REQUIRED = False`** + email-only auth  
   You have both email and username in signup fields. For a B2B SaaS, email-only is cleaner and has less friction. You already have `ACCOUNT_LOGIN_METHOD = {"email"}` â€” the username field in signup is redundant.

5. **`SocialAccountAdapter`** override  
   Would let you auto-assign workspace from invitation on Google OAuth signup â€” currently Google signups bypass the `invite_accepted` flow entirely.

6. **`allauth.mfa`** (TOTP 2FA)  
   Available since allauth 0.56. For a financial app (jewellery loans), 2FA per-user or per-workspace-role (Owner/Admin) is a meaningful security layer.

7. **`allauth.headless`**  
   If you ever add a mobile client or API frontend, allauth's headless mode exposes all auth flows as JSON endpoints without a separate auth library.

8. **Rate limiting / `ACCOUNT_LOGIN_ATTEMPTS_LIMIT`**  
   Not set. Default is 5 attempts/300s. Worth explicitly configuring given financial data.

---

### Priority order

1. Fix the `ACCOUNT_SIGNUP_FIELDS` typo (breaks signup silently)
2. Replace hardcoded Google client_id with a settings variable
3. Uncomment and fix `user_signed_up` â†’ PendingInvitation â†’ Membership flow
4. Add a custom `AccountAdapter` to gate signups to invited users only
5. Enable mandatory email verification
6. Consider TOTP 2FA given the financial domain

Want me to start on any of these?
