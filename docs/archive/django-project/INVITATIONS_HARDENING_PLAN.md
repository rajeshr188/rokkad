---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Plan: Django-Invitations Flow Hardening

Date: 2026-03-28

**TL;DR**: Make membership creation idempotent; remove duplicate-write race condition; enforce signal as single source of truth; add email normalization; add regression tests for edge cases.

## Reference Documentation

For a comprehensive end-to-end guide to the invitation flow, including lifecycle diagrams, data models, URL routing, signal contracts, and troubleshooting, see [INVITATION_FLOW_REFERENCE.md](./INVITATION_FLOW_REFERENCE.md).

## Steps

### Phase 1: Idempotency & Race Condition Removal

#### Step 1.1: Rewrite `create_membership` signal handler (invite_accepted) to be idempotent

**Location**: [apps/orgs/signals.py](../apps/orgs/signals.py#L13) â€” `@receiver(invite_accepted)` handler

**Changes**:
- Use `Membership.objects.get_or_create()` instead of direct `create()`
- Normalize email lookup: `User.objects.filter(email__iexact=email).first()` (case-insensitive)
- If membership already exists: log audit event "MEMBERSHIP_ALREADY_EXISTS" (no-op)
- If membership created: log audit event "MEMBERSHIP_CREATED_FROM_INVITE"
- If user not found: create `PendingInvitation` (unchanged flow)

**Code pattern**:
```python
@receiver(invite_accepted)
def create_membership(sender, **kwargs):
    email = kwargs.get("email")
    invitation = kwargs.get("invitation")
    
    if not invitation:
        return
    
    # Lookup user case-insensitively
    user = User.objects.filter(email__iexact=email).first()
    
    if user:
        membership, created = Membership.objects.get_or_create(
            user=user,
            company=invitation.company,
            defaults={"role": invitation.role}
        )
        if created:
            AuditLog.log(
                "MEMBERSHIP_CREATED_FROM_INVITE",
                user=user,
                company=invitation.company,
                description=f"Membership created from invite acceptance",
                success=True,
                data={"email": email, "role": invitation.role.name}
            )
    else:
        # User not yet registered; create pending
        PendingInvitation.objects.get_or_create(
            email=email,
            company=invitation.company,
            defaults={"role": invitation.role}
        )
```

**Impact**: no more IntegrityError on duplicate signal delivery; idempotent behavior

---

#### Step 1.2: Rewrite `create_membership_on_signup` signal handler (user_signed_up) to be idempotent

**Location**: [apps/orgs/signals.py](../apps/orgs/signals.py#L53) â€” `@receiver(user_signed_up)` handler

**Changes**:
- Query ALL pending invitations for this email (not just first)
- For each pending: use `get_or_create` for membership; delete pending regardless
- Wrap in `transaction.atomic()` to ensure consistent pending cleanup
- Log each membership created and each pending consumed

**Code pattern**:
```python
@receiver(user_signed_up)
def create_membership_on_signup(sender, **kwargs):
    user = kwargs.get("user")
    email = user.email
    
    # Find all pending invitations for this email
    pending_invitations = PendingInvitation.objects.filter(email__iexact=email)
    
    with transaction.atomic():
        for pending in pending_invitations:
            membership, created = Membership.objects.get_or_create(
                user=user,
                company=pending.company,
                defaults={"role": pending.role}
            )
            if created:
                AuditLog.log(
                    "MEMBERSHIP_CREATED_FROM_PENDING",
                    user=user,
                    company=pending.company,
                    description=f"Membership created from pending invite on signup",
                    success=True,
                    data={"role": pending.role.name}
                )
            # Delete pending whether created or already existed
            pending.delete()
```

**Impact**: no orphaned pending invitations; all pending â†’ membership on signup

---

#### Step 1.3: Remove duplicate membership creation from `CustomAcceptInvite` view

**Location**: [apps/orgs/views.py](../apps/orgs/views.py#L300) â€” `CustomAcceptInvite.get()` method

**Changes**:
- Delete the entire if-block at lines 310â€“313: the `Membership.objects.create()` call
- Leave the `return super().get(*args, **kwargs)` call
- Rationale: `invite_accepted` signal (which fires inside `super().post()`) is now the single source of truth

**Code pattern**:
```python
# Before
class CustomAcceptInvite(AcceptInvite):
    def get(self, *args, **kwargs):
        logger.info("CustomAcceptInvite get")
        invite = self.get_object()
        email = invite.email
        user = User.objects.filter(email=email).first()

        if user:
            # DELETE THIS ENTIRE BLOCK
            Membership.objects.create(
                user=user, company=invite.company, role=invite.role
            )

        return super().get(*args, **kwargs)

# After
class CustomAcceptInvite(AcceptInvite):
    def get(self, *args, **kwargs):
        logger.info("CustomAcceptInvite get")
        return super().get(*args, **kwargs)
```

**Impact**: no duplicate membership creation; signal is single source of truth

---

### Phase 2: Pending Invitation Idempotency

#### Step 2.1: Add uniqueness constraint on `PendingInvitation` model

**Location**: [apps/orgs/models.py](../apps/orgs/models.py#L285) â€” `PendingInvitation` Meta class

**Changes**:
```python
class PendingInvitation(models.Model):
    # ... fields ...
    
    class Meta:
        unique_together = ("email", "company")  # ADD THIS LINE
```

**Migration**:
```bash
python manage.py makemigrations apps.orgs
python manage.py migrate
```

**Impact**: database enforces no duplicate pending invites for same email+company

---

### Phase 3: Endpoint Consistency

#### Step 3.1: Unify acceptance logic across both invitation endpoints

**Problem**: You have two acceptance endpoints:
- Package URL: `/invitations/accept-invite/<key>/` â†’ routed to package's `AcceptInvite`
- Custom URL: `/team/invitations/accept/<key>/` â†’ routed to `CustomAcceptInvite`

**Solution**: Both should use the same view and produce identical behavior

**Option A (recommended)**: Remove `CustomAcceptInvite`, use package `AcceptInvite` directly
- [apps/orgs/urls.py](../apps/orgs/urls.py#L54): change `CustomAcceptInvite.as_view()` to `AcceptInvite.as_view()`
- Delete class `CustomAcceptInvite` entirely from [apps/orgs/views.py](../apps/orgs/views.py#L300)
- Both URLs now serve identical behavior via same view

**Option B**: Keep `CustomAcceptInvite` (already cleaned in Phase 1 step 1.3) and verify it calls super correctly

**Verification**: both URLs behave identically (test with same invitation key on both endpoints)

---

### Phase 4: Testing & Validation

#### Step 4.1: Add regression test cases for edge conditions

**Location**: [apps/orgs/tests.py](../apps/orgs/tests.py) or new file `apps/orgs/test_invitations.py`

**Test cases** (use SimpleTestCase + mocks for signal logic; TransactionTestCase for concurrent):

```python
class InvitationSignalTests(SimpleTestCase):
    """Test idempotency of invitation signal handlers"""
    
    def test_existing_user_accepts_invite_creates_membership(self):
        # User exists, invitation link accepted â†’ membership created once
        
    def test_existing_user_reopens_same_invite_link_no_duplicate_membership(self):
        # User accepts invite, then re-opens same link
        # Expected: membership not duplicated, idempotent behavior
        
    def test_non_user_accepts_invite_creates_pending_invitation(self):
        # Non-user opens invite link â†’ pending invitation created
        # No membership yet
        
    def test_non_user_accepts_invite_then_signs_up_creates_membership_once(self):
        # Non-user accepts invite (pending created)
        # Then user signs up with same email
        # Expected: membership created exactly once, pending deleted
        
    def test_duplicate_invite_accepted_signal_idempotent(self):
        # Simulate signal delivered twice (network retry, etc.)
        # Expected: membership created once, no IntegrityError
        
    def test_email_case_variants_resolve_correctly(self):
        # User@Example.com invites user with User@EXAMPLE.com
        # Expected: same user found, membership correct
        
    def test_pending_invitation_unique_constraint_enforced(self):
        # Try to create duplicate pending for same email+company
        # Expected: IntegrityError or get returns existing
```

**Run tests**:
```bash
python manage.py test apps.orgs.test_invitations -v 2
python manage.py test apps.orgs -v 2  # all orgs tests
```

**Expected**: all green, no flaky tests

---

## Relevant Files

- `apps/orgs/signals.py` â€” two signal handlers: `create_membership`, `create_membership_on_signup`
- `apps/orgs/views.py` â€” `CustomAcceptInvite` class (line 300)
- `apps/orgs/models.py` â€” `Membership` (L154), `PendingInvitation` (L285)
- `apps/orgs/urls.py` â€” accept invite endpoints at lines 54, 110
- `apps/orgs/tests.py` or new `apps/orgs/test_invitations.py` â€” test suite

---

## Verification Checklist

- [ ] No IntegrityError on duplicate membership creation attempts
- [ ] Multiple signal deliveries for same invitation produce same result (idempotent)
- [ ] `PendingInvitation` is consumed exactly once per user signup
- [ ] Email case variants (User@Example.com vs user@example.com) resolve correctly
- [ ] Both `/invitations/accept-invite/<key>/` and `/team/invitations/accept/<key>/` behave identically
- [ ] All 6+ edge-case tests pass
- [ ] `python manage.py check` passes
- [ ] `python manage.py test apps.orgs -v 2` all green

---

## Decisions

- **Single source of truth**: `invite_accepted` signal handler for membership grants
- **Email normalization**: use Django ORM `iexact` for case-insensitive lookups
- **Acceptance endpoint unification**: keep both URLs for backward compat, same behavior (Option A preferred)
- **PendingInvitation lifecycle**: consumed on user_signed_up; treated as temporary staging table

---

## Dependencies & Implementation Order

1. **Phase 1** (Idempotency): steps 1.1 â†’ 1.2 â†’ 1.3 (sequential, can't skip)
2. **Phase 2** (Pending uniqueness): step 2.1 (can run after Phase 1)
3. **Phase 3** (Endpoint consistency): step 3.1 (independent; can run in parallel with Phase 2)
4. **Phase 4** (Tests): step 4.1 (after phases 1-3 complete)

**Estimated time**: 
- Phase 1: ~30 min
- Phase 2: ~10 min (migration + model edit)
- Phase 3: ~15 min (remove CustomAcceptInvite)
- Phase 4: ~45 min (write + run tests)
- **Total**: ~2 hours

---

## Out of Scope (Deferred)

- Migration of existing pending invitations (data cleanup) â€” defer if causes backward compat issues
- Social signup auto-provisioning from invite â€” handle in allauth plan if needed
- Invitation expiry enforcement â€” already in package; verify works

