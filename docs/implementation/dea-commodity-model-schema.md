---
status: active
owner: dea
updated: 2026-06-24
tags: [implementation, dea, commodity, schema, metals, accounting]
related:
  - ../adr/2026-06-24-dea-commodity-accounting-layer.md
  - ../adr/2026-06-24-dea-document-voucher-journal-lifecycle.md
  - ../audits/dea_core_accounting_commodity_analysis.md
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - dea-monetary-currency-guardrails.md
---

# DEA Commodity Model Schema Plan

## Summary

This is the Phase 3 schema plan for the DEA commodity accounting layer.

The goal is to add a side-by-side commodity accounting model without disturbing financial double-entry accounting. Financial ledgers, party account transactions, money fields, balance views, and trial balance remain monetary. Commodity records track metal quantity, purity, movement, custody, exposure, fixing, and reporting valuation.

This document started as the pre-migration schema plan. Phase 3 now has the `Commodity` and `CommodityAccount` foundation, default Gold/Silver seed setup, immutable `CommodityMovement`, `ExposureLine`, `RateFixing`, `RateFixingAllocation`, a side-by-side commodity posting service skeleton, commodity position selectors, MVP valuation policy, and valuation read-model foundation implemented/documented; reports and UI remain future slices.

## Non-Negotiable Rules

- Do not represent gold, silver, or metals as `MoneyField` currencies.
- Do not store metal quantity in `amount_currency`, `ClosingBalance_currency`, `TotalDebit_currency`, or `TotalCredit_currency`.
- Do not post metal quantities through `LedgerTransaction` or `AccountTransaction`.
- Do not include commodity quantities in financial trial balance.
- Posted commodity movements are immutable.
- Corrections happen by reversal movement and corrected document, not in-place mutation.
- Business flows must call DEA commodity posting services or facades; views/templates must not create commodity movements directly.

## Proposed File Layout

Initial implementation should keep the model surface small:

| File | Purpose |
|---|---|
| `apps/tenant_apps/dea/models/commodity.py` | Commodity master, commodity accounts, movements, exposures, rate fixing. |
| `apps/tenant_apps/dea/models/__init__.py` | Export commodity models after implementation. |
| `apps/tenant_apps/dea/admin.py` or `admin/commodity.py` | Read/admin surfaces for setup and diagnostics. |
| `apps/tenant_apps/dea/services/commodity_posting.py` | Future command/service for movement/exposure creation. |
| `apps/tenant_apps/dea/selectors/commodity.py` | Future metal balance and position selectors. |
| `apps/tenant_apps/dea/tests/test_commodity_models.py` | Model constraints and immutability tests. |

Do not add UI in the initial model migration task.

## Naming Decision

Use `Commodity` as the model name, with MVP records for `GOLD` and `SILVER`.

Reasoning:

- Jeweller/bullion workflows may later include non-metal commodities or alloy categories.
- Model fields can still use `commodity` while UI labels say metal.
- `rates.Rate` currently uses `metal`; adapters can map `Commodity.code` to existing rate metal choices during the MVP.

## Model: `Commodity`

Master data for gold, silver, and future commodity/metals.

### Fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `code` | `CharField(max_length=16)` | Yes | Tenant-local code. MVP examples: `GOLD`, `SILVER`. Uppercase normalized. |
| `name` | `CharField(max_length=64)` | Yes | Display name. |
| `commodity_type` | `CharField(max_length=16, choices=...)` | Yes | MVP default `METAL`; future `STONE`, `OTHER` if needed. |
| `default_uom` | `CharField(max_length=16, choices=...)` | Yes | MVP default `GRAM`. |
| `is_active` | `BooleanField(default=True)` | Yes | Deactivate instead of delete after use. |
| `metadata` | `JSONField(default=dict, blank=True)` | No | Import/source notes, display preferences. |
| `created_at` | `DateTimeField(auto_now_add=True)` | Yes | Audit metadata. |
| `updated_at` | `DateTimeField(auto_now=True)` | Yes | Audit metadata. |

### Choices

`CommodityType`:

- `METAL`
- `OTHER`

`UnitOfMeasure`:

- `GRAM`
- `KG`
- `TOLA`
- `OUNCE`

MVP balance selectors should normalize to the movement `uom` stored on movement rows and start with `GRAM`. Unit conversions can be deferred unless multi-UOM entry is required immediately.

### Constraints And Indexes

| Constraint/index | Definition |
|---|---|
| Unique code | `UniqueConstraint(fields=["code"], name="uniq_dea_commodity_code")` |
| Code index | `Index(fields=["code"])` |
| Active/type index | `Index(fields=["is_active", "commodity_type"])` |

### Validation

- `code` must be uppercase alphanumeric plus underscore.
- `code` must not be an ISO monetary currency code used by DEA financial currency configuration.
- `code` must not be accepted in financial `MoneyField` currency paths as commodity balance.

## Model: `CommodityAccount`

Balance bucket for metal quantity or metal obligation. This is not a financial GL account.

Examples:

- Owned gold in main vault.
- Silver with karigar.
- Gold receivable from party.
- Gold payable to supplier.
- Metal adjustment account.

### Fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `code` | `CharField(max_length=64)` | Yes | Tenant-local stable code, e.g. `GOLD_MAIN_VAULT`. |
| `name` | `CharField(max_length=128)` | Yes | Human label. |
| `commodity` | `ForeignKey("dea.Commodity", PROTECT)` | Yes | Account is commodity-specific for MVP. |
| `purpose` | `CharField(max_length=32, choices=...)` | Yes | Balance bucket purpose. |
| `party` | `ForeignKey("party.Party", PROTECT, null=True, blank=True)` | No | Required for party receivable/payable/custody purposes. |
| `location_label` | `CharField(max_length=128, blank=True)` | No | MVP location/vault/storage label until a formal location model exists. |
| `financial_control_ledger` | `ForeignKey("dea.Ledger", PROTECT, null=True, blank=True)` | No | Reconciliation reference only; does not hold metal quantity. |
| `is_active` | `BooleanField(default=True)` | Yes | Deactivate instead of delete after use. |
| `metadata` | `JSONField(default=dict, blank=True)` | No | Import/source notes. |
| `created_at` | `DateTimeField(auto_now_add=True)` | Yes | Audit metadata. |
| `updated_at` | `DateTimeField(auto_now=True)` | Yes | Audit metadata. |

### Purpose Choices

| Purpose | Meaning |
|---|---|
| `OWNED_STOCK` | Business-owned commodity stock. |
| `VAULT` | Business-owned custody/location bucket. |
| `KARIGAR_CUSTODY` | Metal issued to karigar/artisan. |
| `PARTY_RECEIVABLE` | Commodity receivable from a party. |
| `PARTY_PAYABLE` | Commodity payable to a party. |
| `ADJUSTMENT` | Manual adjustment suspense/balancing bucket. |
| `LOSS_GAIN` | Physical loss/gain bucket for approved adjustments. |

### Constraints And Indexes

| Constraint/index | Definition |
|---|---|
| Unique code | `UniqueConstraint(fields=["code"], name="uniq_dea_commodity_account_code")` |
| Commodity/purpose index | `Index(fields=["commodity", "purpose"])` |
| Party index | `Index(fields=["party", "commodity", "purpose"])` |
| Active index | `Index(fields=["is_active", "commodity"])` |

### Validation

- Party is required for `PARTY_RECEIVABLE`, `PARTY_PAYABLE`, and `KARIGAR_CUSTODY` when the account represents an external person/business.
- Party should be blank for generic `OWNED_STOCK`, `VAULT`, `ADJUSTMENT`, and `LOSS_GAIN` accounts unless a business-specific reason exists.
- `financial_control_ledger` is optional and must be used only for reconciliation. It must not make the commodity account a GL account.
- Deleting an account with movements should be blocked by `PROTECT` or validation.

## Model: `CommodityMovement`

Immutable posted movement or obligation movement. This is the commodity equivalent of an accounting movement, but it is not a journal entry and not a ledger transaction.

### Fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `movement_no` | `CharField(max_length=64)` | Yes | Human/audit identifier. Can use later numbering service. |
| `movement_date` | `DateField(db_index=True)` | Yes | Business-effective date. |
| `source_content_type` | `ForeignKey(ContentType, PROTECT)` | Yes | Source document/event type. |
| `source_object_id` | `PositiveIntegerField()` | Yes | Source document/event id. |
| `source` | `GenericForeignKey` | Yes | Source document/event. |
| `voucher` | `ForeignKey("dea.Voucher", PROTECT, null=True, blank=True)` | No | Link to financial voucher when event has financial effects. |
| `commodity` | `ForeignKey("dea.Commodity", PROTECT)` | Yes | Metal/commodity. |
| `uom` | `CharField(max_length=16, choices=...)` | Yes | MVP default `GRAM`. |
| `gross_weight` | `DecimalField(max_digits=14, decimal_places=3)` | Yes | Physical gross weight in `uom`. |
| `purity` | `DecimalField(max_digits=7, decimal_places=6)` | Yes | Fraction: `0.916000`, `0.999000`, etc. |
| `fine_weight` | `DecimalField(max_digits=14, decimal_places=3)` | Yes | Primary balance quantity. |
| `from_account` | `ForeignKey("dea.CommodityAccount", PROTECT, related_name="outgoing_movements", null=True, blank=True)` | No | Blank for opening/increase from outside only when movement type allows. |
| `to_account` | `ForeignKey("dea.CommodityAccount", PROTECT, related_name="incoming_movements", null=True, blank=True)` | No | Blank for issue/decrease to outside only when movement type allows. |
| `movement_type` | `CharField(max_length=32, choices=...)` | Yes | Business meaning. |
| `fixed_status` | `CharField(max_length=16, choices=...)` | Yes | `FIXED`, `UNFIXED`, `NOT_APPLICABLE`. |
| `rate` | `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)` | No | Transaction/fixing valuation rate, not metal quantity. |
| `rate_currency` | `CharField(max_length=3, blank=True)` | No | Monetary currency only. MVP `INR` when set. |
| `valuation_currency` | `CharField(max_length=3, blank=True)` | No | Reporting valuation currency. MVP `INR` when set. |
| `valuation_amount` | `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` | No | Monetary valuation amount. |
| `is_reversal_of` | `ForeignKey("self", PROTECT, null=True, blank=True)` | No | Links reversal movement to original. |
| `idempotency_key` | `CharField(max_length=128, db_index=True)` | Yes | Source/event-level dedupe key. |
| `narration` | `TextField(blank=True)` | No | Audit note. |
| `metadata` | `JSONField(default=dict, blank=True)` | No | Posting details/import details. |
| `created_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True)` | No | Actor. |
| `created_at` | `DateTimeField(auto_now_add=True)` | Yes | Audit metadata. |

Do not add `updated_at` if immutable rows do not support edits. If Django/admin convenience requires it, model `save()` must block updates after creation.

### Movement Type Choices

| Type | Meaning |
|---|---|
| `OPENING` | Initial commodity balance. |
| `PURCHASE_RECEIPT` | Commodity received from purchase. |
| `SALE_ISSUE` | Commodity issued/sold. |
| `RATE_FIXING` | Quantity movement or status change due to fixing, if needed. |
| `KARIGAR_ISSUE` | Metal moved to karigar custody. |
| `KARIGAR_RECEIPT` | Metal received back from karigar. |
| `ADJUSTMENT_IN` | Approved increase. |
| `ADJUSTMENT_OUT` | Approved decrease/loss. |
| `REVERSAL` | Reversal of prior movement. |

### Fixed Status Choices

- `FIXED`
- `UNFIXED`
- `PARTIALLY_FIXED`
- `NOT_APPLICABLE`

### Constraints And Indexes

| Constraint/index | Definition |
|---|---|
| Positive gross weight | `CheckConstraint(gross_weight__gt=0)` |
| Positive fine weight | `CheckConstraint(fine_weight__gt=0)` |
| Valid purity | `CheckConstraint(purity__gt=0, purity__lte=1)` |
| Different accounts | Check that `from_account != to_account` when both are set. |
| One side present | Validation requires at least one of `from_account` or `to_account`. |
| Unique idempotency | `UniqueConstraint(fields=["idempotency_key"], name="uniq_dea_commodity_movement_idempotency")` |
| Source index | `Index(fields=["source_content_type", "source_object_id"])` |
| Voucher index | `Index(fields=["voucher"])` |
| Position index | `Index(fields=["commodity", "movement_date"])` |
| Account movement indexes | `Index(fields=["from_account", "movement_date"])`, `Index(fields=["to_account", "movement_date"])` |
| Reversal index | `Index(fields=["is_reversal_of"])` |

### Validation

- `fine_weight` should equal `gross_weight * purity` within a configured tolerance unless an override flag/reason exists.
- `from_account` and `to_account` commodities must match `movement.commodity`.
- `rate_currency` and `valuation_currency` must be monetary currency codes only.
- `rate` and valuation fields are optional for custody-only movement.
- Reversal movement must mirror commodity/uom/fine weight and invert accounts.
- Original movement may have at most one active reversal movement.

### Immutability

After creation:

- No economic field may change.
- No delete if movement has been used in a posted report/fixing/reversal.
- Corrections create a `REVERSAL` movement and a new corrected movement/document.

Implementation can enforce this by:

- overriding `save()` to compare persisted fields on update,
- overriding `delete()`,
- adding service-level tests,
- keeping admin read-only for posted rows.

## Model: `ExposureLine`

Represents open fixed/unfixed commodity exposure for purchase/sale flows. This is not a money receivable/payable and not a GL balance.

### Fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `exposure_no` | `CharField(max_length=64)` | Yes | Human/audit identifier. |
| `source_content_type` | `ForeignKey(ContentType, PROTECT)` | Yes | Source document/event. |
| `source_object_id` | `PositiveIntegerField()` | Yes | Source document/event id. |
| `source` | `GenericForeignKey` | Yes | Source document/event. |
| `voucher` | `ForeignKey("dea.Voucher", PROTECT, null=True, blank=True)` | No | Financial voucher if any. |
| `party` | `ForeignKey("party.Party", PROTECT)` | Yes | Customer/supplier/counterparty. |
| `commodity` | `ForeignKey("dea.Commodity", PROTECT)` | Yes | Metal/commodity. |
| `side` | `CharField(max_length=16, choices=...)` | Yes | `PURCHASE` or `SALE`. |
| `status` | `CharField(max_length=16, choices=...)` | Yes | `OPEN`, `PARTIALLY_FIXED`, `FIXED`, `REVERSED`, `CLOSED`. |
| `fixed_status` | `CharField(max_length=16, choices=...)` | Yes | Initial fixed/unfixed state. |
| `original_fine_weight` | `DecimalField(max_digits=14, decimal_places=3)` | Yes | Original exposure quantity. |
| `open_fine_weight` | `DecimalField(max_digits=14, decimal_places=3)` | Yes | Quantity still unfixed/open. |
| `uom` | `CharField(max_length=16, choices=...)` | Yes | MVP `GRAM`. |
| `rate_basis` | `CharField(max_length=64, blank=True)` | No | Market source, contract term, rate note. |
| `valuation_currency` | `CharField(max_length=3, default="INR")` | Yes | Monetary currency only. |
| `last_valuation_rate` | `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)` | No | Reporting cache only, optional. |
| `last_valuation_amount` | `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` | No | Reporting cache only, optional. |
| `is_reversal_of` | `ForeignKey("self", PROTECT, null=True, blank=True)` | No | Reversal/correction link. |
| `idempotency_key` | `CharField(max_length=128, db_index=True)` | Yes | Source/event dedupe key. |
| `created_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True)` | No | Actor. |
| `created_at` | `DateTimeField(auto_now_add=True)` | Yes | Audit metadata. |
| `updated_at` | `DateTimeField(auto_now=True)` | Yes | Needed because open quantity changes through fixing. |

### Side Choices

- `PURCHASE`
- `SALE`

### Status Choices

- `OPEN`
- `PARTIALLY_FIXED`
- `FIXED`
- `REVERSED`
- `CLOSED`

### Constraints And Indexes

| Constraint/index | Definition |
|---|---|
| Positive original weight | `CheckConstraint(original_fine_weight__gt=0)` |
| Non-negative open weight | `CheckConstraint(open_fine_weight__gte=0)` |
| Open <= original | Validate in `clean()` and service logic. |
| Unique idempotency | `UniqueConstraint(fields=["idempotency_key"], name="uniq_dea_exposure_idempotency")` |
| Source index | `Index(fields=["source_content_type", "source_object_id"])` |
| Party/status index | `Index(fields=["party", "status"])` |
| Commodity/status index | `Index(fields=["commodity", "status"])` |
| Side/status index | `Index(fields=["side", "status"])` |

### Validation

- `valuation_currency` must be monetary only.
- `open_fine_weight` cannot exceed `original_fine_weight`.
- `FIXED` status requires `open_fine_weight = 0`.
- `OPEN` status requires `open_fine_weight > 0`.
- Reversed exposure must not be used for new fixing.

## Model: `RateFixing`

Business document for fixing rate against one or more open exposures.

### Fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `fixing_no` | `CharField(max_length=64)` | Yes | Human/audit identifier. |
| `fixing_date` | `DateField(db_index=True)` | Yes | Business-effective date. |
| `party` | `ForeignKey("party.Party", PROTECT)` | Yes | Counterparty. |
| `commodity` | `ForeignKey("dea.Commodity", PROTECT)` | Yes | Metal/commodity. |
| `side` | `CharField(max_length=16, choices=ExposureLine.side)` | Yes | Purchase or sale fixing. |
| `fine_weight` | `DecimalField(max_digits=14, decimal_places=3)` | Yes | Quantity fixed by this document. |
| `uom` | `CharField(max_length=16, choices=...)` | Yes | MVP `GRAM`. |
| `rate` | `DecimalField(max_digits=14, decimal_places=4)` | Yes | Monetary rate per unit basis. |
| `currency` | `CharField(max_length=3)` | Yes | Monetary currency only. |
| `valuation_amount` | `DecimalField(max_digits=14, decimal_places=2)` | Yes | `fine_weight * rate` after policy rounding. |
| `status` | `CharField(max_length=16, choices=...)` | Yes | Draft/posted/reversed/corrected. |
| `voucher` | `ForeignKey("dea.Voucher", PROTECT, null=True, blank=True)` | No | Financial voucher created when posted. |
| `idempotency_key` | `CharField(max_length=128, db_index=True, blank=True)` | No | Filled on post. |
| `narration` | `TextField(blank=True)` | No | Business note. |
| `created_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` | No | Actor. |
| `updated_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` | No | Actor. |
| `created_at` | `DateTimeField(auto_now_add=True)` | Yes | Audit metadata. |
| `updated_at` | `DateTimeField(auto_now=True)` | Yes | Audit metadata. |

### Allocation Model

MVP can use a simple through model to support partial fixing and future multi-exposure fixing:

`RateFixingAllocation`

| Field | Type | Required | Notes |
|---|---|---:|---|
| `rate_fixing` | `ForeignKey("dea.RateFixing", CASCADE)` | Yes | Parent fixing document. |
| `exposure` | `ForeignKey("dea.ExposureLine", PROTECT)` | Yes | Open exposure being fixed. |
| `fine_weight` | `DecimalField(max_digits=14, decimal_places=3)` | Yes | Quantity fixed from this exposure. |
| `amount` | `DecimalField(max_digits=14, decimal_places=2)` | Yes | Monetary amount allocated. |

If the first implementation wants fewer tables, a single `linked_exposure` FK on `RateFixing` is acceptable only if partial/multi-exposure fixing is explicitly deferred. The roadmap prefers the through model because partial fixing is common in bullion workflows.

### Status Choices

- `DRAFT`
- `POSTED`
- `REVERSED`
- `CORRECTED`

### Constraints And Indexes

| Constraint/index | Definition |
|---|---|
| Unique fixing number | `UniqueConstraint(fields=["fixing_no"], name="uniq_dea_rate_fixing_no")` |
| Positive weight | `CheckConstraint(fine_weight__gt=0)` |
| Positive rate | `CheckConstraint(rate__gt=0)` |
| Positive valuation amount | `CheckConstraint(valuation_amount__gt=0)` |
| Party/status index | `Index(fields=["party", "status"])` |
| Commodity/date index | `Index(fields=["commodity", "fixing_date"])` |
| Voucher index | `Index(fields=["voucher"])` |

### Validation

- Currency must be monetary only.
- Allocation exposure party, commodity, and side must match the fixing document.
- Sum of allocation fine weights must equal fixing fine weight.
- Allocation quantity cannot exceed exposure open fine weight.
- Posted fixing is immutable; correction uses reversal and new fixing.

## Derived Selector: `CommodityPosition`

Do not create a persisted `CommodityPosition` model in MVP.

Implement as selectors over `CommodityMovement`:

- balance by commodity,
- balance by commodity account,
- balance by party,
- balance by location label,
- balance by fixed/unfixed status,
- as-of date balance,
- optional valuation using rates.

Selector output should use explicit quantity fields:

```python
{
    "commodity_code": "GOLD",
    "account_code": "GOLD_MAIN_VAULT",
    "uom": "GRAM",
    "gross_weight": Decimal("100.000"),
    "fine_weight": Decimal("91.600"),
    "valuation_currency": "INR",
    "valuation_amount": Decimal("612345.00"),
}
```

Do not use `Money` objects for `fine_weight`.

## Posting And Idempotency Rules

Commodity posting skeleton now lives in `dea/services/commodity_posting.py`.

Recommended command shapes:

- `post_commodity_movement(payload, actor)`: implemented for direct immutable movement creation.
- `open_exposure(payload, actor)`: implemented for direct exposure creation.
- `reverse_commodity_movement(movement, actor, reason)`: deferred.
- `post_rate_fixing(rate_fixing, actor)`: deferred.

Payloads must include:

- source document identity,
- event type,
- business-effective date,
- commodity code,
- gross weight,
- purity,
- fine weight,
- from/to commodity accounts,
- fixed status,
- rate/valuation fields where applicable.

Idempotency key should be deterministic:

```text
commodity:{source_app}:{source_model}:{source_pk}:{event_type}:{economic_payload_hash}
```

For commodity effects created beside a financial voucher, the financial voucher fingerprint and commodity idempotency key should both be derived from the same business-event payload.

## Financial Reconciliation Rules

Commodity records can reference financial records, but they do not replace them.

Allowed links:

- `CommodityMovement.voucher` links to financial voucher for events with financial effects.
- `CommodityAccount.financial_control_ledger` helps reconcile owned metal value or party obligations.
- `RateFixing.voucher` links to financial voucher that creates monetary AR/AP after fixing.

Forbidden behavior:

- Creating `LedgerTransaction` rows for metal grams.
- Creating `AccountTransaction` rows for commodity receivable/payable.
- Using `ledger_balances` or `account_balances` to report metal balance.

## Migration Strategy

Tenant app model changes require `migrate_schemas`.

Initial migration order:

1. Add `Commodity`.
2. Add `CommodityAccount`.
3. Add `CommodityMovement`.
4. Add `ExposureLine`.
5. Add `RateFixing` and `RateFixingAllocation`.
6. Add seed command or data migration for default `GOLD` and `SILVER` only after model tests pass.

Current implementation state:

- `Commodity` and `CommodityAccount` are implemented in tenant migration `dea.0033`.
- Default `GOLD` and `SILVER` setup is implemented through `apps.tenant_apps.dea.services.commodity_seed.seed_default_commodities()` and the `seed_dea_commodities` command.
- `CommodityMovement` is implemented in tenant migration `dea.0034`.
- `ExposureLine`, `RateFixing`, and `RateFixingAllocation` are implemented in tenant migration `dea.0035`.
- The seed command is intentionally operational/idempotent rather than a data migration, so tenant rollout can run it explicitly after tenant migrations.
- Existing financial currency rows are not migrated into commodity tables automatically.

Do not migrate existing financial currency rows into commodity tables automatically.

Before any production data conversion:

- Run `audit_dea_currency_codes`.
- Review suspicious financial currency values manually.
- Decide per tenant whether values are true monetary currency, import error, or legacy metal-as-currency data.
- Write tenant-specific backfill scripts only after manual verification.

## Admin And Permissions

Initial admin should be conservative:

- `Commodity`: add/edit allowed for accountant/admin.
- `CommodityAccount`: add/edit allowed until movements exist; after movements, restrict economic fields.
- `CommodityMovement`: read-only after creation.
- `ExposureLine`: read-only except service-managed open quantity/status.
- `RateFixing`: draft editable; posted read-only.

Normal staff should not use admin to create commodity records. Staff workflows should eventually use business event documents.

## Required Tests For Model Implementation

### Commodity Tests

- Creates Gold/Silver commodities.
- Enforces unique `code`.
- Normalizes/rejects invalid code shape.
- Rejects commodity codes that conflict with monetary currency guardrails.
- Allows deactivation without deleting historical rows.

### Commodity Account Tests

- Creates owned stock/vault account.
- Creates party receivable/payable account with `party`.
- Rejects party obligation account without party.
- Enforces unique account `code`.
- Blocks deleting account with movements.
- Verifies `financial_control_ledger` does not create financial balance rows.

### Commodity Movement Tests

- Creates movement with gross weight, purity, and fine weight.
- Rejects zero/negative weights.
- Rejects purity <= 0 or > 1.
- Rejects mismatched commodity account commodity.
- Rejects missing both `from_account` and `to_account`.
- Computes or validates fine-weight tolerance.
- Enforces unique idempotency key.
- Blocks mutation after creation.
- Creates reversal movement with inverted accounts.
- Ensures reversal movement offsets selector balance.
- Confirms no `LedgerTransaction` or `AccountTransaction` rows are created by movement creation.

### Exposure Tests

- Creates open purchase exposure.
- Creates open sale exposure.
- Rejects open quantity greater than original quantity.
- Rejects negative open quantity.
- Fixed status requires open quantity zero.
- Reversed exposure cannot be fixed again.
- Enforces idempotency key.

### Rate Fixing Tests

- Creates draft rate fixing.
- Posts partial fixing against open exposure.
- Rejects fixing quantity greater than open exposure.
- Reduces exposure open fine weight.
- Fully fixed exposure moves to fixed/closed status.
- Rejects non-monetary currency.
- Posted fixing is immutable.
- Reversal restores exposure open quantity according to reversal policy.

### Selector Tests

- Metal balance by commodity.
- Metal balance by commodity account.
- Metal balance by party account.
- As-of date balance.
- Reversal offset behavior.
- Trial balance remains unchanged by commodity movements.

### Tenant Tests

- Commodity data is tenant-local.
- Same commodity code can exist in different tenant schemas.
- `migrate_schemas` path is documented for rollout.

## Open Decisions Before Migration

| Decision | Recommendation |
|---|---|
| Persist `CommodityPosition`? | No for MVP. Use selectors first. |
| Add formal `Location` model now? | No. Use `location_label` until inventory/location design stabilizes. |
| Support Tola/Ounce conversion now? | Defer unless UI entry requires it. Store movement `uom`; start with `GRAM`. |
| Add `ValuationSnapshot` now? | Defer. Use reporting selectors with rates. |
| Use `Commodity` or `Metal` model name? | Use `Commodity`; UI can label metal. |
| Use through model for fixing allocation? | Prefer yes; it handles partial/multi-exposure fixing cleanly. |

## Next Implementation Task

Start Phase 4 fixed purchase backend MVP only.

Scope:

- define a small fixed purchase command/service contract
- create financial voucher/journal/account effects through existing canonical posting paths
- create side-by-side commodity movement through commodity posting service
- add idempotency and focused tests

Do not add reports, broad purchase module UI, `ValuationSnapshot`, or unrealized gain/loss accounting in this fixed purchase slice.
