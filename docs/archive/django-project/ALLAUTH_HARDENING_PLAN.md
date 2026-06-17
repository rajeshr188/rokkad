---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Plan: Django-Allauth Hardening & Configuration

Date: 2026-03-28

**TL;DR**: Fix syntax error in signup fields, externalize hardcoded Google client_id, enable email verification, document optional enhancements for 2FA and email-only signup.

## Steps

### 1. Fix `ACCOUNT_SIGNUP_FIELDS` typo â€” missing comma between `"username*"` and `"password1*"`

**Location**: [django_project/settings/base.py](../settings/base.py#L311)

**Change**: 
```python
# Before
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*" "password1*"]

# After
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*"]
```

**Impact**: signup form will correctly parse all three fields

---

### 2. Externalize hardcoded Google client ID from templates

**Locations**: 
- [templates/account/login.html](../../templates/account/login.html#L30)
- [templates/account/signup.html](../../templates/account/signup.html#L19)

**Steps**:
1. Add context processor function to expose `GOOGLE_CLIENT_ID` from Django settings
   - File: `django_project/context_processors.py` (create if doesn't exist; add function if exists)
   - Function: `def google_oauth_context(request)` â€” return `{'GOOGLE_CLIENT_ID': settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('CLIENT_ID', '')}`

2. Register context processor in [django_project/settings/base.py](../settings/base.py)
   - Add to `TEMPLATES[0]['OPTIONS']['context_processors']`: `'django_project.context_processors.google_oauth_context'`

3. Update templates:
   - Replace: `data-client_id="123-secret...apps.googleusercontent.com"`
   - With: `data-client_id="{{ GOOGLE_CLIENT_ID }}"`

4. Settings: Configure Google client ID from environment
   - Add to [django_project/settings/base.py](../settings/base.py) under `SOCIALACCOUNT_PROVIDERS`:
   ```python
   SOCIALACCOUNT_PROVIDERS = {
       "google": {
           "SCOPE": ["profile", "email"],
           "AUTH_PARAMS": {"access_type": "online"},
           "OAUTH_PKCE_ENABLED": True,
           "FETCH_USERINFO": True,
           "CLIENT_ID": env("GOOGLE_CLIENT_ID", default=""),  # from .env
       }
   }
   ```

**Impact**: no hardcoded secrets in source code; credentials read from environment

---

### 3. Enable email verification (optional hardening, recommended for SaaS)

**Location**: [django_project/settings/base.py](../settings/base.py)

**Add**:
```python
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "optional"  # or "mandatory" if stricter policy
```

**Effect**: 
- Confirmation email sent on signup
- User can access app while unverified (if "optional")
- Required to verify before account operations (if "mandatory")

**Rationale**: for a financial SaaS (jewellery loans), unverified email is a fraud/account-recovery risk

---

### 4. Document optional enhancements in ALLAUTH_ENHANCEMENTS.md

**Create**: `django_project/docs/ALLAUTH_ENHANCEMENTS.md`

**Content**: document these for future prioritization
- Email-only signup (remove username from signup fields)
- TOTP 2FA with allauth.mfa (Django 3.2+); requires allauth 0.56+
- Custom AccountAdapter for advanced signup UX
- Social signup auto-provisioning from invitations

---

## Relevant Files

- `django_project/settings/base.py` â€” allauth settings, ACCOUNT_SIGNUP_FIELDS, SOCIALACCOUNT_PROVIDERS
- `django_project/context_processors.py` â€” new/updated context processor for Google client ID
- `templates/account/login.html` â€” hardcoded client_id at line 30
- `templates/account/signup.html` â€” hardcoded client_id at line 19
- `templates/account/password_*.html` â€” other account templates (do not modify; use custom if needed)

---

## Verification

- [ ] `python manage.py check` â€” no settings errors
- [ ] Test signup form renders all three fields: email, username, password1
- [ ] Test Google OAuth login with externalized client ID
- [ ] (Optional) Enable email verification; test confirmation email flow
- [ ] No syntax errors in settings or templates

---

## Decisions

- **Email verification**: optional (not mandatory yet); change value later if stricter policy needed
- **Google credentials**: read from env var `GOOGLE_CLIENT_ID` with fallback to empty string for dev
- **No custom AccountAdapter yet**: invitations flow handles company membership gating
- **Username retention**: keep for now (can remove later if simplifying to email-only)

---

## Further Considerations (Out of Scope)

- **TOTP 2FA**: requires allauth 0.56+; defer to Phase 2
- **Custom AccountAdapter**: only if post-signup UX refinement is needed
- **Social signup auto-provisioning**: handle in invitations plan (not allauth adapter)

