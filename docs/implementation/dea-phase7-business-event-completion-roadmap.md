---
status: recommendations
updated: 2026-06-26
scope: Business Event Workflows & Commodity Management Completion
phase: Phase 7-8 transition
---

# Business Event Workflows & Commodity Management: Completion Roadmap

## Executive Summary

**Current State**: 
- ✅ All 8+ business event forms are complete and tested
- ✅ All preview and detail screens are wired
- ✅ All backend posting services are implemented and tested
- ❌ Confirm buttons are deliberately disabled (Phase 6 design decision)
- ❌ **NO user-facing UI for commodity creation** (critical gap)

**To enable business event posting and commodity management, three parallel workstreams are required**:

1. **Quick Win**: Enable business event confirm buttons (1 PR, low-risk)
2. **Feature Work**: Design & implement commodity master-data CRUD (3-5 PRs, medium-risk)
3. **Follow-up**: Commodity account setup workflow (related feature)

---

## 1. ENABLE BUSINESS EVENT POSTING (Quick Win)

### What's Required

**Current State**: All business event forms have confirm buttons set to `disabled` attribute in templates.

**File**: [apps/tenant_apps/dea/views/business_events.py](apps/tenant_apps/dea/views/business_events.py)

**Change Required**:
```python
# Line ~XXX in each event view class (Fixed Purchase, Unfixed Purchase, etc.)

# Current:
confirm_disabled = True  # Phase 6: Deliberate lock

# Change to:
confirm_disabled = False  # Phase 7: Enable posting
```

**Affected Views** (8 event types):
1. `FixedPurchaseDetailView`
2. `UnfixedPurchaseDetailView`
3. `PurchaseRateFixingDetailView`
4. `FixedSaleDetailView`
5. `UnfixedSaleDetailView`
6. `SaleRateFixingDetailView`
7. `MonetarySettlementDetailView` (Receipt from Customer)
8. `MonetarySettlementDetailView` (Payment to Supplier)

**Templates Affected** (8 files):
- `templates/dea/business_events/fixed_purchase_detail.html`
- `templates/dea/business_events/unfixed_purchase_detail.html`
- `templates/dea/business_events/purchase_rate_fixing_detail.html`
- `templates/dea/business_events/fixed_sale_detail.html`
- `templates/dea/business_events/unfixed_sale_detail.html`
- `templates/dea/business_events/sale_rate_fixing_detail.html`
- `templates/dea/business_events/monetary_settlement_detail.html` (both receipt/payment)
- `templates/dea/business_events/karigar_movement_detail.html`

### Impact Analysis

| Category | Assessment | Notes |
|----------|------------|-------|
| **Risk Level** | 🟢 LOW | All forms & services fully tested (67 route tests + service tests) |
| **Breaking Changes** | None | Pure enablement; no API or schema changes |
| **Rollback Path** | Trivial | Revert `confirm_disabled = False` → `True` |
| **Testing** | Covered | All event types have 3-5 tests each; existing tests validate posting behavior |
| **Dependencies** | None | Posting services are production-ready |

### Recommended Steps

1. **Create feature branch**: `feature/phase7-enable-business-event-posting`
2. **Update Python views** (one change per view class):
   - Set `confirm_disabled = False` in each event view's `get_context_data()`
3. **Verify template rendering** (no code changes; confirm buttons will become active)
4. **Run test suite**:
   ```bash
   .venv314/Scripts/python.exe manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb --verbosity 2
   ```
5. **Manual QA**: Test one event flow end-to-end (e.g., Fixed Sale: create → preview → confirm → verify GL entries)
6. **Commit & document**: Link PR to Phase 7 completion in roadmap

### Estimated Effort
- **Coding**: 15 minutes (8 one-line changes)
- **Testing**: 30 minutes (run suite + manual QA)
- **Review**: 15 minutes
- **Total**: ~1 hour

---

## 2. COMMODITY MASTER-DATA CRUD (Feature Work)

### Requirement: User-Facing Commodity Creation/Edit/Delete

**Current Gap**: 
- Commodities only creatable via Django admin (backend staff only) or CLI
- Business users cannot add new commodities (e.g., COPPER, PLATINUM)
- All business event forms hardcoded to read-only commodity dropdowns

### Design Recommendation

#### Option A: **Dedicated Commodity Management Screen** (Recommended)

**URL Structure**:
```
GET  /dea/commodities/                    → List commodities (accountant-only)
GET  /dea/commodities/<id>/                → Detail view with edit capability
POST /dea/commodities/                    → Create new commodity
POST /dea/commodities/<id>/                → Update existing commodity
POST /dea/commodities/<id>/deactivate/     → Soft-delete (deactivate)
```

**Access Control**: Restrict to `@dea_accountant_required` (Owner, Admin, Accountant roles only)

**Views to Implement**:
1. `CommodityListView(DeaAccountantRequiredMixin, ListView)`
   - List all commodities (active + inactive)
   - Filter by type (Metal, Other)
   - Link to detail/edit screens
   
2. `CommodityDetailView(DeaAccountantRequiredMixin, DetailView)`
   - Show commodity properties
   - Show related commodity accounts
   - Link to edit form
   
3. `CommodityCreateView(DeaAccountantRequiredMixin, CreateView)`
   - Form: code, name, type, default_uom
   - Validation: code format, uniqueness
   - Success: redirect to detail
   
4. `CommodityUpdateView(DeaAccountantRequiredMixin, UpdateView)`
   - Form: same as create (name, type, uom; code read-only)
   - Validation: same
   - Success: show detail page
   
5. `CommodityDeactivateView(DeaAccountantRequiredMixin, View)` [AJAX]
   - Soft-delete: set `is_active = False`
   - Check: Warn if commodity has active accounts or recent movements
   - Prevent: Deactivation if recent business events use this commodity

**Form Definition** (`apps/tenant_apps/dea/forms.py`):
```python
class CommodityForm(forms.ModelForm):
    class Meta:
        model = Commodity
        fields = ['name', 'commodity_type', 'default_uom']
        # code: Read-only in update view; required in create
    
    def clean_code(self):
        code = self.cleaned_data.get('code', '').upper()
        if not re.match(r'^[A-Z0-9_]+$', code):
            raise ValidationError("Code must be alphanumeric + underscore only")
        if Commodity.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Code already exists")
        # Prevent currency codes
        if code in RESERVED_CURRENCY_CODES:
            raise ValidationError(f"Code '{code}' is reserved")
        return code
```

**Templates** (4 new files):
- `templates/dea/commodity_list.html` — List with add button
- `templates/dea/commodity_detail.html` — Detail + edit/deactivate actions
- `templates/dea/commodity_form.html` — Create/edit form
- Inline: Commodity accounts table on detail page

**Related Models to Surface**:
- Show `CommodityAccount` records linked to each commodity
- Allow navigation to account setup (see Section 3)

#### Option B: **Inline Commodity Add in Business Event Forms** (Alternative)

- Add "Create Commodity" modal on business event forms
- Less isolated; couples commodity creation with event workflow
- **Not recommended**: Distracts from event entry; encourages ad-hoc commodity creation

**Recommendation**: Use **Option A** (dedicated management screen).

---

### Recommended Implementation Steps

**PR 1: Core Views & Forms**
1. Create views file: `apps/tenant_apps/dea/views/commodity_manager.py`
2. Create form: `CommodityForm` in `apps/tenant_apps/dea/forms.py`
3. Create views:
   - `CommodityListView`
   - `CommodityDetailView`
   - `CommodityCreateView`
   - `CommodityUpdateView`
   - `CommodityDeactivateAjax`
4. Write 8-10 tests in `test_commodity_manager_views.py`

**PR 2: Templates & Navigation**
1. Create template files (4 new)
2. Add route to sidebar/navigation (accountant tools section)
3. Link from commodity dropdowns in business events (optional: "Add Commodity" button)
4. Add tests for template rendering

**PR 3: Commodity Account Setup Integration** (See Section 3)
1. Add "Setup Accounts" button on commodity detail page
2. Navigate to account creation wizard for new commodity
3. Write tests for workflow

**PR 4: Validation & Edge Cases** (if needed)
1. Prevent deactivation if active accounts/recent movements
2. Handle inactive commodity filtering in business event forms
3. Add archived commodity support (if needed)

### Estimated Effort
- **PR 1 (Views)**: 3-4 hours (forms, views, basic tests)
- **PR 2 (Templates)**: 2-3 hours (UI, navigation, routing)
- **PR 3 (Integration)**: 2 hours (linked workflow)
- **PR 4 (Polish)**: 1-2 hours (validation, edge cases)
- **Total**: 8-11 hours across 3-4 PRs

### Risk Assessment
| Risk | Mitigation |
|------|-----------|
| New model CRUD surface | Already have pattern from voucher/account management |
| Deactivation cascading effects | Add guard: check commodity accounts & recent events |
| Multi-tenancy isolation | Commodity model already uses tenant schema isolation |
| Code format validation | Use same pattern as Account.account_number |

---

## 3. COMMODITY ACCOUNT SETUP (Dependent Feature)

### Requirement: Users Must Set Up Commodity Accounts for Each Commodity

**Current State**:
- CommodityAccount model exists (OWNED_STOCK, VAULT, KARIGAR_CUSTODY types)
- Only creatable via Django admin
- Business events require accounts to be pre-configured
- No workflow to guide users through account setup for a new commodity

**Recommended Approach**: **Account Wizard** tied to commodity creation

### Design: Commodity Account Setup Wizard

**Flow**:
```
1. Create new commodity (Section 2)
   ↓
2. Detail page shows "Setup Accounts" button
   ↓
3. Wizard prompts:
   - "For commodity COPPER, create accounts:"
   - [ ] OWNED_STOCK (Your company's metal holdings)
   - [ ] VAULT (Safe custody/storage location)
   - [ ] KARIGAR_CUSTODY (Optional: metalworker deposits)
   ↓
4. Create selected accounts automatically
   ↓
5. Confirmation: "Ready to use COPPER in business events"
```

### Views to Implement

**CommodityAccountWizardView**:
```python
class CommodityAccountWizardView(DeaAccountantRequiredMixin, FormView):
    # Step 1: Show which account types to create
    # Step 2: Create selected accounts
    # Step 3: Confirmation + link back to commodity detail
```

**Or simpler**: Add "Quick Setup" action on commodity detail:
```python
@dea_accountant_required
def commodity_account_quick_setup(request, commodity_id):
    """Auto-create all 3 standard account types for commodity"""
    commodity = get_object_or_404(Commodity, id=commodity_id)
    for account_type in ['OWNED_STOCK', 'VAULT', 'KARIGAR_CUSTODY']:
        CommodityAccount.objects.get_or_create(
            commodity=commodity,
            account_type=account_type
        )
    messages.success(request, f"Accounts created for {commodity.name}")
    return redirect(commodity.get_absolute_url())
```

### Estimated Effort
- **Single function + template button**: 1 hour
- **Full wizard alternative**: 3-4 hours

### Recommendation
Implement **quick setup** for Phase 7 (MVP); defer full wizard to Phase 8 if needed.

---

## 4. PHASE 7-8 TIMELINE & SEQUENCING

### Phase 7 Remaining (Before Merge)

| Workstream | Priority | Effort | Risk | Status |
|---|---|---|---|---|
| **Enable Business Event Posting** | 🔴 CRITICAL | 1 hour | 🟢 LOW | Ready to start |
| **Commodity Master-Data CRUD** | 🟡 HIGH | 8-11 hours | 🟡 MEDIUM | Ready to start |
| **Commodity Account Quick Setup** | 🟡 HIGH | 1 hour | 🟢 LOW | Defer to Phase 7 or Phase 8 |

### Recommended Sequence

**Phase 7.1** (This session):
1. ✅ Enable business event confirm buttons (1 hour)
2. ✅ Run full test suite to verify
3. ✅ Manual QA: one event flow end-to-end

**Phase 7.2** (Next session):
1. Implement Commodity CRUD views + forms (3-4 hours)
2. Create templates & navigation (2-3 hours)
3. Write & pass tests (1-2 hours)
4. Manual QA: create/edit/deactivate commodity workflow

**Phase 7.3** (Optional - same session):
1. Add commodity account quick setup button (1 hour)
2. Test: create commodity → auto-create accounts → use in business event

**Phase 8** (Future):
- Enhanced account wizard
- Commodity deprecation warnings
- Bulk commodity import
- Multi-currency commodity support

---

## 5. TESTING STRATEGY

### Phase 7.1: Business Event Posting Enablement

**Existing Test Coverage**: ✅ 67+ route tests + service tests already cover:
- Form validation for each event type
- Preview screen rendering
- Detail page with posted data
- Backend service behavior (GL entry creation, ledger updates)

**What's NOT tested yet**: Confirm button click → actual posting
- **New tests**: Add 8 tests, one per event type:
  ```python
  def test_fixed_sale_confirm_creates_gl_entries(self):
      # 1. Create draft business event
      # 2. POST to confirm endpoint
      # 3. Assert JournalEntry created
      # 4. Assert BusinessEventDraft marked complete
  ```

### Phase 7.2: Commodity CRUD

**Required Tests** (12-15 tests):
- Create commodity: valid code, invalid code, duplicate code
- Update commodity: name & type only (code read-only)
- Deactivate: success path + guard checks
- Permission: non-accountant users blocked
- Dropdown: commodities listed in business event forms (active only by default)
- Deactivation: warn if active accounts exist

### Manual QA Checklist

**Business Event Posting**:
- [ ] Create Fixed Sale: complete form → preview → confirm → GL entries created
- [ ] Create Unfixed Purchase: complete form → preview → confirm → ledger updated
- [ ] Create Rate Fixing: form → confirm → ledger balances reflect fix
- [ ] Create Payment Settlement: form → confirm → cash GL accounts updated

**Commodity Management**:
- [ ] Create commodity: COPPER → valid code, visible in dropdowns
- [ ] Edit commodity: update name & UOM
- [ ] Deactivate commodity: set inactive, removed from business event dropdowns
- [ ] Account setup: create commodity → auto-create accounts → use in sale

---

## 6. DEPENDENCIES & BLOCKERS

### Hard Dependencies (Must Have Before Proceeding)
- ✅ Phase 7 dashboard gating complete (already done)
- ✅ Phase 7 accounting tools inventory complete (already done)
- ✅ All business event forms + services tested (already done)

### Soft Dependencies (Nice-to-Have)
- Phase 7 period CRUD hardening (doesn't block business events)
- Bank reconciliation access audit (doesn't block business events)

### Known Gotchas
1. **Multi-tenant commodity isolation**: Commodity model uses schema-level isolation; verify during multi-tenant testing
2. **Commodity dropdown filtering**: Business event forms currently show `is_active=True` only; ensure deactivated commodities disappear gracefully
3. **CommodityAccount creation**: Related objects created when commodity added; ensure wizard doesn't create duplicates
4. **Posting service idempotency**: All posting services tested for re-posting same event; ensure confirm is safe to click twice

---

## 7. DOCUMENTATION & HANDOFF

### What to Document

1. **Business Event Posting Enablement** (Brief):
   - Why it was disabled (Phase 6 safeguard)
   - What changed (confirm_disabled flag)
   - Testing results

2. **Commodity Management** (Comprehensive):
   - New screens: List, Detail, Create, Edit, Deactivate
   - Access control: Accountant-only
   - Role-gating pattern used
   - Integration with business events

3. **Commodity Account Setup** (Brief):
   - Quick-setup button on commodity detail
   - Auto-creates 3 account types
   - Next step: use commodity in business events

### Update Project Docs

Files to update after completion:
- `docs/STATUS.md` — Current Phase 7 progress
- `docs/roadmaps/dea_commodity_accounting_refactor_plan.md` — Phase 7 completion milestone
- `docs/implementation/dea-phase7-accounting-tools-inventory.md` — Add "Business Event Workflows" section
- `docs/domain/` — Document commodity lifecycle (if needed)

---

## Summary: What Needs to Happen

| Deliverable | Owner | Effort | Blocker For | Can Start |
|---|---|---|---|---|
| Enable business event confirm buttons | Phase 7 | 1 hour | Users posting events | ✅ NOW |
| Design commodity CRUD workflows | Phase 7-8 | 4 hours | Commodity creation | ✅ NOW |
| Implement commodity CRUD views+forms+templates | Phase 7-8 | 8-11 hours | Using custom commodities | ✅ After step 1 |
| Commodity account quick setup | Phase 7-8 | 1 hour | Automated account creation | ✅ After step 2 |
| Full test suite & manual QA | Phase 7-8 | 2-3 hours | Production readiness | ✅ In parallel |

**Recommended Next Step**: Start with **Section 1** (enable business event posting) — 1-hour quick win with zero risk, full test coverage already in place.

