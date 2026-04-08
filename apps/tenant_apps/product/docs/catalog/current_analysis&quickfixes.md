I’ll inspect the product app models and related architecture files first, then provide a focused code review with concrete enhancement recommendations prioritized by impact.

Searched for files matching `**/product/**`, 20 matches

Searched for files matching `**/products/**`, no matches

Searched for regex `class .*Product|app_name\s*=\s*["']product|INSTALLED_APPS`, 53 results

I found the product app under apps/tenant_apps/product; next I’m reading its model modules and related stock/domain models to evaluate architecture quality end-to-end.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models)

Searched for files matching `**/apps/tenant_apps/product/models/**/*.py`, 4 matches

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/product.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/stock.py#1-1), lines 1 to 380

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/price.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/stock.py#381-381), lines 381 to 404

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/__init__.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/README.md)

I’ve finished the core model files and found several architecture smells already; I’m now checking managers, attribute plumbing, and alternative model implementations to separate active design from legacy/experimental code.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/managers.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/attributes.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/new_product.py#1-1), lines 1 to 460

Searched for regex `new_product|from \.new_product|import new_product` (`**/apps/tenant_apps/product/**`), no results

Searched for regex `StockLot|self\.stock|updated_on|self\.eight|stock_batch` (`**/apps/tenant_apps/product/models/stock.py`), 22 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/stock.py#1-1), lines 1 to 260

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/stock.py#240-240), lines 240 to 404

Searched for files matching `**/apps/tenant_apps/product/migrations/*.py`, 5 matches

Searched for regex `HStoreField|jattributes|StockBalance|PricingTierProductPrice|unique_together|constraints|Index` (`**/apps/tenant_apps/product/**/*.py`), 55 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/tests.py)

I’ve confirmed the app has very few tests and several legacy indicators; next I’m reading the key forms/views that exercise these models so the architecture review reflects real usage, not just schema shape.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/forms.py#1-1), lines 1 to 360

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/stock.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/producttype.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/migrations/0001_initial.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/migrations/0002_initial.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/migrations/0004_auto_views.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/apps.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/__init__.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/urls.py#1-1), lines 1 to 260

Searched for regex `class MPPTMeta|sku = models.CharField|max_length=4|get_pure_by_cost|stock=self.stock|stock_batch=self|updated_on|def transact\(|journal_entry\)|self\.stock !=|self\.eight|StockLot|barcode__icontains|stockstatement_formset|update//|def get_bal\(|pass|print\(` (`**/apps/tenant_apps/product/**/*.py`), 49 results

Searched for regex `def stock_delete|messages\.error\(|require_http_methods|name="stock_journalentry"` (`**/apps/tenant_apps/product/views/stock.py`), 6 results

Searched for regex `from \.models import \*|from \.attributes import \*|from \.category import \*|from \.product import \*|from \.stock import \*` (`**/apps/tenant_apps/product/**/*.py`), 7 results

Searched for regex `def merge_lot|node\.merge\(\)|def merge\(self, lot` (`**/apps/tenant_apps/product/**/*.py`), 4 results

Searched for text `new_product` (`**/*.py`), no results

**Findings (ordered by severity)**

1. High: Stock audit path is currently broken and will crash at runtime.  
stock.py uses `stock=self.stock` inside `Stock.audit()`, but `Stock` has no `stock` field. It should likely be `stock=self`.  
stock.py passes `stock_batch=self`, but `StockStatement` has no `stock_batch` field. This will raise a TypeError on create.

2. High: Merge flow is not executable in current code path.  
stock.py calls `node.merge()` with no argument.  
stock.py defines `merge(self, lot)` requiring a lot.  
Inside merge, more errors exist:
- stock.py: references `self.stock` which does not exist.
- stock.py: typo `self.eight`.
- stock.py: helper uses `StockLot`, which is not defined in this module.

3. High: Transaction API and model constraints are inconsistent.  
stock.py requires `journal_entry` in `transact(...)`.  
stock.py has non-nullable `journal_entry` FK.  
But stock.py, stock.py, and stock.py pass `journal_entry=None`, and split calls omit it entirely. This will fail on save.

4. High: Stock search references a non-existent field.  
stock.py filters on `barcode__icontains`, but `Stock` does not define `barcode` in stock.py.

5. High: Stock statement formset view uses an undefined symbol.  
stock.py and stock.py call `stockstatement_formset(...)`, but that formset is not defined/imported in the file.

6. Medium: Duplicate field declaration on Stock masks schema intent.  
stock.py defines `sku` and stock.py defines `sku` again. The second one silently overwrites the first at class definition time.

7. Medium: Utility methods contain logic bugs.  
- stock.py: `self.get_weight * self.purchase_touch` uses method object instead of call.
- stock.py: uses `updated_on`, but model field is `updated`.
- product.py: `get_bal` is stubbed and returns nothing.

8. Medium: MPTT meta class typo prevents intended ordering behavior.  
product.py and price.py use `MPPTMeta` instead of MPTT expected meta naming.

9. Medium: Routing typo may cause brittle URL behavior.  
urls.py contains double slash in update route path.

10. Medium: Weak observability and noisy debug output in core model/form logic.  
Print debugging is present in attribute plumbing and forms:
- attributes.py
- attributes.py
- forms.py

11. Medium: Test coverage is effectively absent for this app.  
tests.py contains only placeholder text.

12. Low/Architecture: Namespace design uses wildcard exports/imports heavily, increasing coupling and ambiguity.  
- __init__.py
- forms.py
- __init__.py

---

**Core architecture review**

Current core architecture is split into three useful domains:

1. Catalog domain: Category, ProductType, Product, ProductVariant, images, attributes in product.py.  
2. Inventory domain: Stock, Movement, StockTransaction, StockStatement, read-model style StockBalance in stock.py.  
3. Pricing domain: PricingTier, tier prices, customer-specific Price in price.py.

This is a good foundation for a modular product app. The main issue is not domain decomposition, but consistency and execution safety. There is a partial event-ledger concept in inventory (transactions + statements + accounting link), but implementation is currently fragmented and includes dead/incomplete paths.

---

**Enhancement recommendations**

1. Stabilize inventory invariants first (highest ROI).  
- Fix all broken Stock methods and merge/split flows.  
- Decide one rule for accounting link:
  - either every StockTransaction requires JournalEntry (strict), or
  - JournalEntry is optional and only mandatory for posted financial movements.
- Enforce with model constraints and service-level validation.

2. Introduce an Inventory service layer and remove business logic from views/forms.  
- Create explicit application services like record_stock_in, split_stock, merge_stock, post_stock_transaction.  
- Keep models thin and deterministic.  
- Move side effects (journal creation, status recompute, lot id generation) into services with atomic transactions.

3. Strengthen schema constraints and indexing.  
- Add unique constraint on pair pricing_tier + product in tier pricing table.  
- Add check constraints for non-negative quantity/weight and sane decimal ranges.  
- Add indexes on hot query fields: variant, status, created, movement_type, journal_entry.

4. Simplify attribute storage strategy.  
Today both HStore and JSON are used together on Product and ProductVariant in product.py.  
Pick one direction:
- If flexibility needed: JSONB only with typed validation and GIN indexes.
- If correctness and reporting needed: normalized assigned-attribute tables (you already have a stronger pattern in new_product.py, though it appears unused).

5. Reduce implicit imports and improve module boundaries.  
- Replace wildcard imports with explicit symbols in forms/views/models init.  
- Expose a narrow public API per package.  
This reduces accidental name collisions and improves static analysis quality.

6. Build a focused test matrix for the critical workflows.  
Priority tests:
- StockTransaction creation with/without JournalEntry according to chosen rule.
- Split and merge invariants: conservation of quantity/weight.
- Stock audit correctness against transaction ledger.
- ProductType attribute combination generation and uniqueness behavior.
- Price fallback and tier resolution logic.

7. Clean migration and legacy artifacts.  
- Validate whether custom view migration logic is still needed in 0004_auto_views.py.  
- Remove dead code paths and stale references to undefined models like StockLot.

---

**Suggested implementation sequence**

1. Fix runtime-breaking issues in stock model and stock views.  
2. Define and codify inventory-accounting contract (required vs optional journal link).  
3. Add tests around stock flows before further refactor.  
4. Refactor imports and move workflow logic into services.  
5. Revisit attribute architecture and price model constraints.

---

**Open assumptions/questions**

1. Should every inventory movement be financially posted immediately, or only specific movement types?  
2. Is Stock intended to represent a lot/batch entity, or a mutable aggregate per variant? Current code mixes both models.  
3. Is the read-model view StockBalance expected to be authoritative, or a convenience projection?

If you want, I can next produce a concrete refactor patch set for step 1 only (runtime break fixes) so you can ship a safe baseline before larger architecture changes.


Let me do a thorough read of all catalog-domain files before reviewing.  

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/attributes.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/product.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/forms.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/product.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/filters.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/productvariant.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/tables.py#1-1), lines 1 to 100

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/producttype.py#60-60), lines 60 to 223

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/image.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/category.py)

I now have everything I need for a thorough analysis. Here is the complete catalog domain review.

---

## Catalog Domain — Architecture Review

### Domain inventory

| Model | Role | Active |
|---|---|---|
| `Category` | MPTT hierarchy (gold/silver/etc.) | ✅ |
| `ProductType` | Template for products (ring/chain/etc.) | ✅ |
| `Attribute` + `AttributeValue` | Shared key-value taxonomy | ✅ |
| `Product` | Concrete item per type+attribute combination | ✅ |
| `ProductVariant` | Sellable unit (SKU) of a Product | ✅ |
| `ProductImage` + `VariantImage` | Photo catalogue | ✅ |
| All of new_product.py | Alternative, richer model design | ❌ never imported anywhere |

---

### Bugs (broken behavior in production)

**1. `MPPTMeta` typo — MPTT ordering is silently ignored**

product.py (also price.py):
```python
class MPPTMeta:                  # wrong — django-mptt looks for MPTTMeta
    order_insertion_by = ["name"]
```
Django-MPTT never sees this class. Category nodes insert in arbitrary order.

---

**2. `ProductVariant.get_attributes()` calls the wrong method**

product.py:
```python
def get_attributes(self):
    return get_product_attributes_data(self.product)  # should be variant-level attributes, not product-level
```
`get_product_attributes_data` reads `product.product_type.product_attributes`, which are product-wide attributes, not the variant-specific ones. The method always returns the wrong set.

---

**3. `ProductImageForm` cannot upload images**

forms.py:
```python
class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["alt"]          # image field is missing
```
`image = models.ImageField(blank=False)` on the model. With this form, the create view (`ProductImageCreateView`) will always fail validation because `image` is required but never provided.

---

**4. `product_edit` silently creates a duplicate variant when none exists**

product.py:
```python
variant = product.variants.first()      # returns None if no variants
variant_form = ProductVariantForm(request.POST or None, instance=variant, prefix="variant")
```
If the product has no variant yet and `has_variants=False`, passing `instance=None` creates a new `ProductVariant` on every save. Repeated edits produce duplicate variants.

---

**5. `Product.__iter__` breaks Django's prefetch cache**

product.py:
```python
def __iter__(self):
    if not hasattr(self, "__variants"):
        setattr(self, "__variants", self.variants.all())  # fires a new query
    return iter(getattr(self, "__variants"))
```
The view calls `Product.objects.prefetch_related("variants")`, which stores results in `product._prefetched_objects_cache["variants"]`. `__iter__` ignores that cache entirely and issues a fresh query. The prefetch is wasted.

---

**6. `display_product(translated=True)` raises `AttributeError`**

product.py:
```python
product = self.product.translated    # AttributeError: Product has no 'translated'
variant_display = str(self.translated)  # same
```
`TranslationProxy` is only wired in new_product.py, not in the active models. Any caller passing `translated=True` crashes.

---

**7. Category delete is GET-based — CSRF-unsafe destructive action**

category.py:
```python
def category_delete(request, slug):
    category.delete()              # fires on GET, no confirmation
```
This also silently cascade-deletes every `Product` under the category (from the `CASCADE` FK).

---

**8. `get_attributes_display_map` has an N+1 query bug**

attributes.py:
```python
for attribute in attributes:
    value = obj.attributes.get(str(attribute.pk))
    if value:
        choices = {str(a.pk): a for a in attribute.values.all()}   # 1 query per attribute
```
One DB query per attribute in the loop. For a product type with 6 attributes this fires 6 queries. Fix: `AttributeValue.objects.filter(attribute__in=attributes)` once, then group in Python.

---

### Architecture issues

#### A. Dual attribute storage is the biggest structural problem

Both `Product` and `ProductVariant` carry two redundant fields:

```python
attributes = HStoreField(...)    # {str(attr_pk): str(value_pk)}
jattributes = models.JSONField() # {attr_name: value_value}
```

These store the same semantic information in two different formats. Problems:

- **Synchronization**: They are only kept in sync when saved through `ProductForm`/`ProductVariantForm`. Any direct `.update()`, signal, import, or management command that touches one and not the other produces inconsistent state.
- **Reference vs display**: `attributes` stores PKs (FK-like references with no actual FK constraint). If an `AttributeValue` is deleted or renamed, `attributes` silently points to a dangling PK. `jattributes` stores the display name, which goes stale when an `AttributeValue`'s `value` field is updated.
- **Type loss**: HStore encodes everything as strings. Numbers, booleans in attribute values are stringified.
- **No DB index**: Neither field has a GIN index defined (common in PostgreSQL for JSONB/HStore), so filtering products by attribute value requires a full scan.
- **Decision**: Choose one. `jattributes` (JSONField) is the correct direction because JSON is a superset of HStore, PostgreSQL has native JSONB GIN indexing, and it allows richer types. The form save logic already writes both, so the migration reduces to dropping HStore and consolidating reads.

#### B. new_product.py is a discarded but superior attribute design

new_product.py implements a fully normalized attribute assignment system:

- `AttributeProduct` associates an `Attribute` to a `ProductType` with sort order
- `AssignedProductAttribute` links a specific `Product` to selected `AttributeValue`s
- This is referentially constrained (actual FKs, not string PKs)
- Supports ordering attributes within a product type
- Supports multiple values per attribute per product
- Supports filtering by attribute efficiently (JOIN-based, indexable)

This design is strictly better for catalog use. The file should either be adopted or deleted, not left as dead code.

#### C. `ProductType` has no uniqueness constraint on `name`

Two product types named "Ring" can be created. Since `Product.name` is generated from `product_type.name + attributes`, duplicate product type names produce product name collisions that are caught only by the `unique=True` constraint on Product — at save time with a cryptic IntegrityError.

#### D. `product_code` and `sku` are both unique identifiers with no defined semantic distinction

product.py:
```python
sku = models.CharField(max_length=100, unique=True)
product_code = models.CharField(max_length=100, unique=True)
```
Both are required, both are unique. The form doesn't expose either, and `generate_products_and_variants` uses UUID for `product_code` and auto-generates `sku` from names. No comment in the code distinguishes their purpose. One should be removed or their roles explicitly scoped (e.g., `sku` = human-readable, `product_code` = system-internal barcode).

#### E. `ProductVariantForm` exposes only `name` — SKU and code are uneditable via UI

forms.py:
```python
class Meta:
    model = ProductVariant
    fields = ["name"]
```
After a variant is generated (with a UUID product_code), there's no way to edit the `sku` or `product_code` through any UI. They can only be changed via admin or direct DB.

#### F. `VariantImage` has no ordering field

The M2M between `ProductVariant` and `ProductImage` via `VariantImage` has no `sort_order` or `is_primary` field. There's no way to specify which image is the hero shot for a variant. `get_first_image()` uses `images[0]` by insertion order, which is arbitrary.

#### G. `generate_products_and_variants` has a hardcoded category assumption

producttype.py:
```python
"category": Category.objects.first()   # silent assumption
```
If no categories exist, or the first category is wrong, silently assigns the wrong one. Should be user-specified.

---

### Summary table

| Issue | Severity | Type | File |
|---|---|---|---|
| `MPPTMeta` typo | Medium | Bug | product.py |
| `get_attributes()` wrong receiver | High | Bug | product.py |
| `ProductImageForm` missing `image` | High | Bug | forms.py |
| `product_edit` creates duplicate variant | High | Bug | product.py |
| `__iter__` ignores prefetch cache | Medium | Bug | product.py |
| `display_product(translated=True)` crash | Low | Bug | product.py |
| `category_delete` via GET | High | Security | category.py |
| N+1 in attribute display map | Medium | Perf | attributes.py |
| Dual HStore+JSON attribute storage | High | Architecture | product.py |
| new_product.py dead code (better design) | High | Architecture | new_product.py |
| `ProductType` no unique name | Medium | Architecture | product.py |
| `sku`/`product_code` undefined semantic distinction | Medium | Architecture | product.py |
| `ProductVariantForm` missing `sku`, `product_code` | Medium | Architecture | forms.py |
| `VariantImage` no sort/primary field | Low | Architecture | product.py |
| Print debugging in attribute logic | Low | Quality | attributes.py |

---

### Recommended implementation sequence

**Phase 1 — Fix bugs that corrupt data or break UI**
1. Fix `ProductImageForm` to include `image` field
2. Fix `product_edit` to guard against `variant = None`
3. Fix `category_delete` to require POST + confirmation (also add `LoginRequiredMixin`)
4. Fix `MPPTMeta` → `MPTTMeta` on `Category` and `PricingTier`
5. Fix `ProductVariant.get_attributes()` to use variant-level attributes

**Phase 2 — Performance and consistency**
1. Fix `Product.__iter__` to use Django's prefetch cache
2. Fix N+1 in `get_attributes_display_map`
3. Add `unique=True` to `ProductType.name`
4. Remove `print()` calls from attributes.py

**Phase 3 — Attribute architecture decision** (requires migration)
- Either consolidate HStore → JSONField, add GIN index, enforce referential integrity via a signal/constraint
- Or adopt the normalized design from new_product.py (larger migration, much better long-term)

Want me to start implementing Phase 1 fixes now?


Let me re-read the relevant sections of both files to give a precise, code-grounded explanation.  

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/product.py#70-70), lines 70 to 160

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/new_product.py#375-375), lines 375 to 475

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/new_product.py#475-475), lines 475 to 577

Here is the concrete, line-by-line comparison.

---

## Why new_product.py has a superior attribute design

### The current design — one blob per object

```
Product
  attributes  = HStoreField  →  {"14": "37", "15": "42"}   ← Attribute PK → AttributeValue PK
  jattributes = JSONField     →  {"Metal": "Gold", "Colour": "Yellow"}
```

Both fields encode the same fact: "this product's Metal attribute has value Gold". You get two copies, two formats, no enforcement.

---

### What new_product.py does instead — four dedicated relational tables

```
ProductType ─── AttributeProduct  ─── Attribute ─── AttributeValue
                     │                                    │
                (sort_order)                         (sort_order)
                     │
               AssignedProductAttribute  ←── Product
                     │
                   values (M2M) ────────────────────────── AttributeValue
```

The four key models:

**`AttributeProduct`** — the junction between `ProductType` and `Attribute`:
```python
class AttributeProduct(SortableModel):      # SortableModel adds sort_order int field
    attribute    = FK(Attribute)
    product_type = FK(ProductType)
    class Meta:
        unique_together = (("attribute", "product_type"),)  # each attr appears once per type
        ordering = ("sort_order", "pk")                     # display order is stored
```

**`AssignedProductAttribute`** — the junction between `Product` and its chosen values:
```python
class AssignedProductAttribute(BaseAssignedAttribute):
    product    = FK(Product, related_name="attributes")
    assignment = FK(AttributeProduct)           # which type-level assignment
    values     = M2M(AttributeValue)            # which values were chosen
    class Meta:
        unique_together = (("product", "assignment"),)
```

Parallel pair for variants: `AttributeVariant` and `AssignedVariantAttribute`.

---

### Concrete problems the normalized design solves

#### 1. Referential integrity — values can't go stale

Current design:
```python
# In Product.attributes (HStore): {"14": "37"}
# If AttributeValue pk=37 is deleted → orphan PK, no error, silently wrong

AttributeValue.objects.filter(pk=37).delete()     # succeeds, Product.attributes now broken
```

Normalized design:
```python
# AssignedProductAttribute.values is a real M2M to AttributeValue
# Django cascades the M2M row automatically when the AttributeValue is deleted
# Product always reflects the current set of actual values
```

#### 2. Multiple values per attribute per product

Current design: one value per attribute per product, hard-coded in the dict:
```python
{"Metal": "Gold"}   # can only have one value for Metal
```

Normalized design:
```python
# AssignedProductAttribute.values = M2M(AttributeValue)
# One assignment can hold {"Gold", "Rose Gold"} — multi-select attributes work naturally
```

This matters for jewellery: "Available in Gold and Silver" is a real product attribute.

#### 3. Display ordering is a stored fact, not a naming convention

Current design: `generate_name_from_values` sorts by `attribute_pk`:
```python
return "/".join(
    str(attribute_value).strip()
    for attribute_pk, attribute_value in sorted(
        attributes_dict.items(), key=lambda x: x[0]   # sorted by PK, arbitrary
    )
)
```
The order is determined by when you created the `Attribute` rows. Rename or recreate one and the order silently shifts.

Normalized design:
```python
class AttributeProduct(SortableModel):    # sort_order = IntegerField
    ordering = ("sort_order", "pk")
```
You explicitly drag-and-drop to set display order per product type. The `product_attributes_sorted()` queryset method on `AttributeQuerySet` returns them in that order.

#### 4. Attribute-based filtering is a proper JOIN, not a JSON scan

Current design — to find "all Gold rings":
```python
Product.objects.filter(jattributes__Metal="Gold")
# PostgreSQL: full table scan unless you create a manual GIN index
# The query plan uses the JSON operator -> which cannot use a btree index
```

Normalized design:
```python
Product.objects.filter(
    attributes__values__name="Gold",
    attributes__assignment__attribute__name="Metal"
)
# Standard FK joins, can use btree indexes on every column involved
# Django ORM generates efficient SQL with proper JOIN predicate
```

#### 5. Input validation is modelled, not implicit

Current `Attribute` model:
```python
class Attribute(models.Model):
    name = models.CharField(max_length=50)
    slug = AutoSlugField(...)
    # That's it. No type info.
```

new_product.py's `Attribute`:
```python
class Attribute(ModelWithMetadata):
    input_type = models.CharField(
        choices=AttributeInputType.CHOICES,    # DROPDOWN, MULTISELECT, DATE, NUMERIC, etc.
        default=AttributeInputType.DROPDOWN,
    )
    value_required = models.BooleanField(default=False)
    is_variant_only = models.BooleanField(default=False)
    visible_in_storefront = models.BooleanField(default=True)
    filterable_in_storefront = models.BooleanField(default=True)
    filterable_in_dashboard = models.BooleanField(default=True)
```

Each attribute declares how it should be rendered (dropdown vs free text vs date), whether it's required, and whether it's filterable. The current design puts all of this logic in form code (`ModelChoiceOrCreationField` check in `AttributesMixin.prepare_fields_for_attributes`), so it's repeated wherever attributes are shown.

---

### But is migration realistic for you right now?

Honestly, implementing the full normalized design requires:
- 4 new tables
- Data migration from JSON blobs into normalized rows
- Rewriting `AttributesMixin`, `get_saved_attributes`, `get_attributes_display_map`
- Updating all templates that display attributes

That is a large, careful migration. The right near-term move is:

**Step 1 (now)** — Drop `HStoreField`, keep only `jattributes` (JSONField). Removes one broken copy, simplifies the form save, requires one migration + deleting `attributes =` field and its references.

**Step 2 (later, when ready)** — Adopt normalized tables from new_product.py with a data migration from `jattributes`. At that point `jattributes` becomes the intermediary that feeds the migration script, then gets dropped too.

The JSONField consolidation is low-risk and gives you immediate benefit (less sync surface, one source of truth). The normalized design is the long-term end state and new_product.py already has it written — it just needs to be hooked in.

Want me to implement Step 1 — remove `HStoreField.attributes` from both `Product` and `ProductVariant` and consolidate everything onto `jattributes`?