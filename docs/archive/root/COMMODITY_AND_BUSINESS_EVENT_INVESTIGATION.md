---
status: archived
date: 2026-06-26
scope: Commodity UI gaps and Business Event workflow completeness
tags: [dea, commodity, business-events, ui, forms]
---

# Commodity Management UI & Business Event Workflow Investigation

Historical investigation for the retired DEA application. Code paths and findings
below describe that revision; they are not current implementation instructions.

## 1. COMMODITY MANAGEMENT UI STATUS

### Current State: **NO USER-FACING UI FOR COMMODITY CREATION**

Commodities are **read-only** in the user-facing application. There is **zero support for users to create, edit, or delete commodities** through any web form.

#### Where Commodities Currently Exist

| Location | Access Type | Purpose |
|----------|------------|---------|
| Django Admin (backend-only) | Admin interface | Backend staff commodity CRUD |
| `seed_dea_commodities` mgmt command | CLI | Tenant seeding: GOLD, SILVER (idempotent) |
| `FixedPurchasePreviewForm.commodity` | Dropdown (read-only) | Fixed purchase selection from active commodities |
| `UnfixedPurchasePreviewForm.commodity` | Dropdown (read-only) | Unfixed purchase selection |
| `FixedSalePreviewForm.commodity` | Dropdown (read-only) | Fixed sale selection |
| `UnfixedSalePreviewForm.commodity` | Dropdown (read-only) | Unfixed sale selection |
| `KarigarMovementPreviewForm.commodity` | Dropdown (read-only) | Karigar custody selection |
| Metal Balance Report filter | Dropdown (read-only) | Report filtering |
| Exposure Report filter | Dropdown (read-only) | Report filtering |
| Valuation Report filter | Dropdown (read-only) | Report filtering |

#### Model Definition

**File**: [apps/tenant_apps/dea/models/commodity.py](../../../apps/tenant_apps/dea/models/commodity.py#L28-L90)

**Structure**:
```python
class Commodity(models.Model):
    code = CharField(max_length=16, unique, db_index=True)
    name = CharField(max_length=64)
    commodity_type = ChoiceField(METAL, OTHER) → defaults METAL
    default_uom = ChoiceField(GRAM, KG, TOLA, OUNCE) → defaults GRAM
    is_active = BooleanField(default=True)
    metadata = JSONField(blank)
    created_at, updated_at = DateTimeFields
```

**Validation Rules**:
- Code: Must be uppercase alphanumeric + underscore only
- Code: Cannot be a monetary currency code (INR, USD, etc.)
- Name: Required
- Default UOM: One of the four weight units

#### Admin Interface

**File**: [apps/tenant_apps/dea/admin.py](../../../apps/tenant_apps/dea/admin.py#L21-L26)

- Registered in Django admin
- List display: code, name, type, uom, is_active
- Search: code, name
- Filter: type, uom, is_active
- **NOT exposed in workspace user interface**

#### Seeding Process

**File**: [apps/tenant_apps/dea/management/commands/seed_dea_commodities.py](../../../apps/tenant_apps/dea/management/commands/seed_dea_commodities.py)

**Default commodities created**:
- GOLD (Metal, Gram)
- SILVER (Metal, Gram)

**Idempotency**: Service idempotently creates/updates seed records. Tenant init runs this automatically.

### KEY GAPS IDENTIFIED

| Gap | Impact | Blocker for | Current Workaround |
|-----|--------|------------|-------------------|
| **No create UI form for commodities** | Users cannot add new commodities (e.g., COPPER, PLATINUM) via web | Business event expansion | Use Django admin or management command |
| **No commodity account UI** | Related: Users cannot set up commodity accounts (OWNED_STOCK, VAULT, KARIGAR_CUSTODY) | Any purchase/sale of custom commodity | Django admin only |
| **Read-only commodity dropdowns** | Business event forms hardcoded to `is_active=True` commodities | No inactive commodity management | Cannot deprecate commodities without breaking forms |
| **No multi-tenancy isolation in admin** | Commodities are global, not per-tenant | Risk: Commodity codes collide across tenants | Mitigated by unique constraint within schema context |

---

## 2. BUSINESS EVENT WORKFLOW TABLE

### Form Completeness & Status by Event Type

| Event Type | Form Class | Form Complete | Preview URL | Preview Form Visible | Detail Template | Posting Wired | Confirm Button | Backend Service | Tests |
|---|---|---|---|---|---|---|---|---|---|
| **Fixed Purchase** | `FixedPurchasePreviewForm` | ✅ Complete | `/dea/business-events/fixed-purchase/` | ✅ Yes | `fixed_purchase_detail.html` | ✅ Yes | ❌ **Disabled** | `post_fixed_purchase()` | ✅ 5 tests |
| **Unfixed Purchase** | `UnfixedPurchasePreviewForm` | ✅ Complete | `/dea/business-events/unfixed-purchase/` | ✅ Yes | `unfixed_purchase_detail.html` | ✅ Yes | ❌ **Disabled** | `post_unfixed_purchase()` | ✅ 5 tests |
| **Purchase Rate Fixing** | `PurchaseRateFixingPreviewForm` | ✅ Complete | `/dea/business-events/purchase-rate-fixing/` | ✅ Yes | `purchase_rate_fixing_detail.html` | ✅ Yes | ❌ **Disabled** | `post_purchase_rate_fixing()` | ✅ 5 tests |
| **Fixed Sale** | `FixedSalePreviewForm` | ✅ Complete | `/dea/business-events/fixed-sale/` | ✅ Yes | `fixed_sale_detail.html` | ✅ Yes | ❌ **Disabled** | `post_fixed_sale()` | ✅ 5 tests |
| **Unfixed Sale** | `UnfixedSalePreviewForm` | ✅ Complete | `/dea/business-events/unfixed-sale/` | ✅ Yes | `unfixed_sale_detail.html` | ✅ Yes | ❌ **Disabled** | `post_unfixed_sale()` | ✅ 5 tests |
| **Sale Rate Fixing** | `SaleRateFixingPreviewForm` | ✅ Complete | `/dea/business-events/sale-rate-fixing/` | ✅ Yes | `sale_rate_fixing_detail.html` | ✅ Yes | ❌ **Disabled** | `post_sale_rate_fixing()` | ✅ 5 tests |
| **Receipt from Customer** | `MonetarySettlementPreviewForm` | ✅ Complete | `/dea/business-events/settlement/` | ✅ Yes | `monetary_settlement_detail.html` | ✅ Yes | ❌ **Disabled** | `post_customer_receipt()` | ✅ 3 tests |
| **Payment to Supplier** | `MonetarySettlementPreviewForm` | ✅ Complete | `/dea/business-events/settlement/` | ✅ Yes | `monetary_settlement_detail.html` | ✅ Yes | ❌ **Disabled** | `post_supplier_payment()` | ✅ 3 tests |
| **Karigar Issue Metal** | `KarigarMovementPreviewForm` | ✅ Complete | `/dea/business-events/karigar/` | ✅ Yes | `karigar_movement_detail.html` | ✅ Yes | ❌ **Disabled** | `post_karigar_issue()` | ✅ 3 tests |
| **Karigar Receipt Metal** | `KarigarMovementPreviewForm` | ✅ Complete | `/dea/business-events/karigar/` | ✅ Yes | `karigar_movement_detail.html` | ✅ Yes | ❌ **Disabled** | `post_karigar_receipt()` | ✅ 3 tests |

### Form Field Completeness

#### Fixed Purchase Form
**File**: [apps/tenant_apps/dea/forms_business_events.py](../../../apps/tenant_apps/dea/forms_business_events.py#L18-L82)

```
✅ source_reference (CharField)
✅ purchase_date (DateField)
✅ supplier_account (ModelChoiceField → Account)
✅ inventory_ledger (ModelChoiceField → Ledger)
✅ payable_ledger (ModelChoiceField → Ledger)
✅ commodity (ModelChoiceField → Commodity, is_active=True only)
✅ gross_weight (DecimalField, ≥0.001)
✅ purity (DecimalField, 6 decimals)
✅ fine_weight (DecimalField, ≥0.001)
✅ from_commodity_account (ModelChoiceField → CommodityAccount)
✅ to_commodity_account (ModelChoiceField → CommodityAccount)
✅ money_amount (DecimalField, ≥0.01)
✅ currency (ChoiceField: INR only for MVP)
✅ narration (CharField, optional)

Validation:
✅ Currency must be INR
✅ From ≠ to commodity account
✅ Both accounts must belong to selected commodity
```

#### Unfixed Purchase Form
**File**: [apps/tenant_apps/dea/forms_business_events.py](../../../apps/tenant_apps/dea/forms_business_events.py#L85-L158)

```
✅ source_reference
✅ purchase_date
✅ party (ModelChoiceField → Party, exclude ARCHIVED)
✅ commodity (is_active=True only)
✅ gross_weight, purity, fine_weight
✅ from_commodity_account
✅ to_commodity_account
✅ rate_basis (CharField, optional)
✅ valuation_currency (INR only)
✅ last_valuation_rate (DecimalField, optional)
✅ narration

Validation:
✅ Valuation currency must be INR
✅ From ≠ to commodity account
✅ Both accounts must belong to selected commodity
```

#### Purchase & Sale Rate Fixing Forms
**File**: [apps/tenant_apps/dea/forms_business_events.py](../../../apps/tenant_apps/dea/forms_business_events.py#L161-L350)

```
Purchase Rate Fixing:
✅ source_reference
✅ exposure (ModelChoiceField → ExposureLine, side=PURCHASE, status=OPEN|PARTIALLY_FIXED)
✅ fixing_date
✅ fine_weight
✅ rate (INR per unit)
✅ supplier_account
✅ inventory_ledger
✅ payable_ledger
✅ currency (INR only)
✅ narration

Validation:
✅ Over-fixing rejection (fine_weight ≤ exposure.open_fine_weight)
✅ Exposure party vs account party match

Sale Rate Fixing:
✅ Similar structure with customer_account, receivable/revenue ledgers
```

#### Fixed & Unfixed Sale Forms
**File**: [apps/tenant_apps/dea/forms_business_events.py](../../../apps/tenant_apps/dea/forms_business_events.py#L353-L496)

```
Fixed Sale:
✅ source_reference
✅ sale_date
✅ customer_account
✅ receivable_ledger
✅ revenue_ledger
✅ commodity (is_active=True only)
✅ gross_weight, purity, fine_weight
✅ from_commodity_account (owned/vault only)
✅ money_amount
✅ currency (INR only)
✅ narration

Unfixed Sale:
✅ Similar to Fixed Sale but with party, rate_basis, valuation_currency, last_valuation_rate
```

#### Monetary Settlement Form
**File**: [apps/tenant_apps/dea/forms_business_events.py](../../../apps/tenant_apps/dea/forms_business_events.py#L502-L615)

```
✅ settlement_type (CUSTOMER_RECEIPT | SUPPLIER_PAYMENT)
✅ source_reference
✅ event_date
✅ party_account (customer for receipt, supplier for payment)
✅ cash_or_bank_ledger
✅ counterparty_ledger (receivable for receipt, payable for payment)
✅ money_amount
✅ reference_number (for idempotency)
✅ currency (INR only)
✅ payment_method (CASH, CHEQUE, BANK_TRANSFER, etc.)
✅ narration

Validation:
✅ Currency must be INR
✅ Reference number required and trimmed
```

#### Karigar Movement Form
**File**: [apps/tenant_apps/dea/forms_business_events.py](../../../apps/tenant_apps/dea/forms_business_events.py#L618-L720)

```
✅ movement_type (KARIGAR_ISSUE | KARIGAR_RECEIPT)
✅ source_reference
✅ event_date
✅ karigar (Party, exclude ARCHIVED)
✅ commodity (is_active=True only)
✅ gross_weight, purity, fine_weight
✅ from_commodity_account
✅ to_commodity_account (custody for issue, owned/vault for receipt)
✅ narration

Validation:
✅ From ≠ to commodity account
✅ Both accounts must belong to selected commodity
✅ Issue: destination must be KARIGAR_CUSTODY with party match
✅ Receipt: source must be KARIGAR_CUSTODY with party match
```

---

## 3. PREVIEW & DETAIL WORKFLOW STATUS

### Preview Screens (All Forms Visible & Functional)

Each event type has a **preview-only screen** where:

| Aspect | Status |
|--------|--------|
| **Form visible** | ✅ All 8 event types show forms |
| **Form accepts input** | ✅ POST on "Preview" button |
| **Preview renders** | ✅ Builds read-only impact preview |
| **Draft persists** | ✅ `BusinessEventDraft` row created/updated |
| **Readiness checklist** | ✅ Shows blocking/passing checks |
| **Confirm button visible** | ✅ Yes, but **DISABLED** |
| **Confirm button functional** | ❌ **Intentionally disabled** |

**Example**: Fixed Purchase Preview at `/dea/business-events/fixed-purchase/`
```
LEFT COLUMN:
- Business Facts Form (inputs: source_reference, purchase_date, accounts, weights, etc.)
- Preview Button (enabled)
- Confirm Button (disabled)

RIGHT COLUMN (after preview):
- Status badge
- Read-only preview of business facts
- Accounting impact (journal entries that WOULD be created)
- Commodity impact (movements that WOULD be created)
```

### Detail/Result Screens (Read-Only, Shows Posted Results)

Each event type has a **detail page** at `/<draft_id>/` showing:

| Content | Shows | Creates Side Effects |
|---------|-------|---------------------|
| Saved draft facts | ✅ Business facts from saved preview | ❌ No |
| Posting readiness | ✅ Checklist of passing/failing conditions | ❌ No |
| Accounting impact | ✅ If posted: Voucher, Journal, Ledger/Account rows | ❌ Only if already posted |
| Commodity impact | ✅ If posted: Movement rows, Exposure rows | ❌ Only if already posted |
| Confirm button | ✅ Yes, POST-only to `/confirm/` | ✅ **Yes - triggers posting** |

---

## 4. POSTING STATUS BY EVENT TYPE

### Backend Services (All Complete & Tested)

| Event | Service | File | Tests | Status |
|-------|---------|------|-------|--------|
| Fixed Purchase | `post_fixed_purchase()` | `services/fixed_purchase.py` | ✅ 5 | ✅ Complete, idempotent |
| Unfixed Purchase | `post_unfixed_purchase()` | `services/unfixed_purchase.py` | ✅ 5 | ✅ Complete, idempotent |
| Purchase Rate Fixing | `post_purchase_rate_fixing()` | `services/rate_fixing.py` | ✅ 10 | ✅ Complete, idempotent |
| Fixed Sale | `post_fixed_sale()` | `services/fixed_sale.py` | ✅ 5 | ✅ Complete, idempotent |
| Unfixed Sale | `post_unfixed_sale()` | `services/unfixed_sale.py` | ✅ 5 | ✅ Complete, idempotent |
| Sale Rate Fixing | `post_sale_rate_fixing()` | `services/rate_fixing.py` | ✅ 5 | ✅ Complete, idempotent |
| Customer Receipt | `post_customer_receipt()` | `services/monetary_settlement.py` | ✅ 3 | ✅ Complete, idempotent |
| Supplier Payment | `post_supplier_payment()` | `services/monetary_settlement.py` | ✅ 3 | ✅ Complete, idempotent |
| Karigar Issue | `post_karigar_issue()` | `services/karigar.py` | ✅ 3 | ✅ Complete, idempotent |
| Karigar Receipt | `post_karigar_receipt()` | `services/karigar.py` | ✅ 3 | ✅ Complete, idempotent |

### Confirm Handoff Services (Complete But UI Disabled)

**File**: [apps/tenant_apps/dea/services/business_event_posting.py](../../../apps/tenant_apps/dea/services/business_event_posting.py)

All 8 event types have handoff services that:
1. Row-lock the previewed `BusinessEventDraft`
2. Reject stale payload/readiness failures
3. Map normalized draft payload into posting payload
4. Delegate to backend posting service
5. Return result with created/duplicate flags

```python
confirm_fixed_purchase_draft(draft_id, actor)
confirm_unfixed_purchase_draft(draft_id, actor)
confirm_purchase_rate_fixing_draft(draft_id, actor)
confirm_fixed_sale_draft(draft_id, actor)
confirm_unfixed_sale_draft(draft_id, actor)
confirm_sale_rate_fixing_draft(draft_id, actor)
confirm_monetary_settlement_draft(draft_id, actor)
confirm_karigar_movement_draft(draft_id, actor)
```

### Confirm Endpoints (Wired But Disabled in UI)

**File**: [apps/tenant_apps/dea/views/business_events.py](../../../apps/tenant_apps/dea/views/business_events.py)

All 8 event types have POST-only routes:
- `/dea/business-events/fixed-purchase/<draft_id>/confirm/`
- `/dea/business-events/unfixed-purchase/<draft_id>/confirm/`
- etc.

**Endpoint Status**:
- ✅ Routes exist and are functional
- ✅ Calls handoff services
- ✅ Handles idempotent duplicate submits
- ✅ Gated by owner/admin/accountant roles
- ✅ Redirects to detail page with result
- ❌ **UI confirm button DISABLED** (JavaScript disabled state)

---

## 5. KEY BLOCKERS FOR COMPLETION

### BLOCKER 1: Confirm Button Disabled in Templates
**Status**: ❌ **Intentionally Blocked** (Phase 6 checkpoint)  
**Impact**: Users cannot post any business events from UI  
**Root Cause**: Phase 6 design decision to disable confirm until Phase 7+ cleanup  
**Location**: All 8 templates (`_preview.html` files, line ~45)  
**Code**:
```html
<button type="submit" name="action" value="confirm" 
        class="btn btn-outline-secondary" 
        {% if confirm_disabled %}disabled{% endif %}>
    Confirm posting
</button>
```
**View Logic** [business_events.py](../../../apps/tenant_apps/dea/views/business_events.py#L193-L207):
```python
confirm_disabled = True  # Hardcoded in all preview views
```
**Unblock**: Change `confirm_disabled = True` to `confirm_disabled = False` (requires Phase 7 completion)

### BLOCKER 2: No Commodity Creation UI
**Status**: ❌ **Gap Identified**  
**Impact**: Users cannot add new commodity types (e.g., COPPER, PLATINUM)  
**Workaround**: CLI `seed_dea_commodities --schema <name>` or Django admin  
**Next Step**: Design commodity master-data CRUD UI as new feature slice

### BLOCKER 3: No Commodity Account Creation UI
**Status**: ❌ **Gap Identified**  
**Impact**: Users cannot set up commodity accounts (OWNED_STOCK, VAULT, KARIGAR_CUSTODY)  
**Workaround**: Django admin only  
**Related**: Blocks custom commodity workflow setup

### BLOCKER 4: Multi-Tenancy Isolation for Commodity Admin
**Status**: ⚠️ **Mitigated**  
**Issue**: Django admin is global; commodities could collide  
**Mitigation**: Unique constraint on `code` within tenant schema context  
**Risk**: Low for multi-tenant SaaS if admin access is workspace-scoped

---

## 6. SUMMARY

### Commodity Management
- **Current**: ZERO user-facing UI for commodity CRUD
- **Read-only**: Commodities only appear as dropdowns in business event forms
- **Admin**: All management through Django admin (backend staff only)
- **Seeding**: Default GOLD/SILVER created via management command
- **Gap**: No way for business users to add/manage commodities

### Business Event Workflows
- **Forms**: All 8 event types ✅ Complete and functional
- **Preview**: All screens ✅ Render forms and show side-effect-free previews
- **Detail**: All screens ✅ Show draft/result data when posted
- **Backend Services**: All 8 ✅ Complete, tested, idempotent
- **Posting**: All wired ✅ BUT confirm button is **DISABLED**
- **Status**: Phase 6 checkpoint complete; Phase 7 cleanup pending

### Readiness for Production
| Item | Ready | Blockers |
|------|-------|----------|
| Form validation & preview | ✅ Yes | None |
| Backend posting logic | ✅ Yes | None |
| Confirm endpoint | ⚠️ Partial | Confirm button disabled in UI |
| Business event UI | ❌ No | Confirm disabled by design |
| Commodity management | ❌ No | No user-facing UI exists |
| Role-based access | ✅ Yes | Confirm gated to owner/admin/accountant |

---

## 7. RECOMMENDED NEXT TASKS

### Phase 7 Cleanup (Current)
1. ✅ Finish legacy surface gating audit (in progress)
2. ✅ Document accounting tools inventory
3. Next: Enable confirm button endpoints for Phase 6 workflows (requires Phase 7 completion)

### Phase 8 (Future)
1. Enable confirm button in templates
2. Run full integration tests with posting enabled
3. Publish business event workflows to production

### Phase 9+ (Feature Expansion)
1. Design commodity master-data CRUD UI
2. Design commodity account setup workflow
3. Add tax/FX handling to fixed purchase/sale
4. Add advanced settlement allocation screens

---

## Appendix: File Inventory

### Models
- [apps/tenant_apps/dea/models/commodity.py](../../../apps/tenant_apps/dea/models/commodity.py) - Commodity, CommodityAccount, CommodityMovement

### Forms
- [apps/tenant_apps/dea/forms_business_events.py](../../../apps/tenant_apps/dea/forms_business_events.py) - All 8 event form classes (720 lines)

### Views
- [apps/tenant_apps/dea/views/business_events.py](../../../apps/tenant_apps/dea/views/business_events.py) - All preview/detail/confirm routes

### Services
- `apps/tenant_apps/dea/services/fixed_purchase.py`
- `apps/tenant_apps/dea/services/unfixed_purchase.py`
- `apps/tenant_apps/dea/services/fixed_sale.py`
- `apps/tenant_apps/dea/services/unfixed_sale.py`
- `apps/tenant_apps/dea/services/rate_fixing.py`
- `apps/tenant_apps/dea/services/monetary_settlement.py`
- `apps/tenant_apps/dea/services/karigar.py`
- `apps/tenant_apps/dea/services/business_event_posting.py` - Handoff services

### Templates
- [templates/dea/business_events/](../../../templates/dea/business_events/) - 17 templates
  - 8 `*_preview.html` (input forms + previews)
  - 8 `*_detail.html` (read-only results)
  - 1 `dashboard.html` (event list)

### Tests
- [apps/tenant_apps/dea/tests/test_business_event_scaffold_views.py](../../../apps/tenant_apps/dea/tests/test_business_event_scaffold_views.py) - UI/route tests
- [apps/tenant_apps/dea/tests/test_business_event_posting_service.py](../../../apps/tenant_apps/dea/tests/test_business_event_posting_service.py) - Handoff service tests
- [apps/tenant_apps/dea/tests/test_*_service.py](../../../apps/tenant_apps/dea/tests/) - Individual service tests (5 tests each)
