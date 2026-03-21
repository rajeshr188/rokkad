I have the data from my reads. Let me build the plan now. 

Created memory file [](file:///c%3A/Users/rajes/AppData/Roaming/Code/User/workspaceStorage/7914ab2b6b5df244df460c4b9f715f8d/GitHub.copilot-chat/memory-tool/memories/ZjFkMmM3MmMtZjAzMi00OWY2LTk5YjUtOWI2Mjg4MTVjYzE0/plan.md)

Here's the plan:

---

## Plan: Adopt Normalized Attribute Tables

**TL;DR** — Replace `jattributes` JSONField with four normalized DB tables from new_product.py. `jattributes` stays alive as the data bridge for the migration script, then gets dropped. Four phases, app keeps working throughout.

---

### Why normalized is strictly better than jattributes

| Property | jattributes (now) | Normalized |
|---|---|---|
| Referential integrity | None — rename `AttributeValue` and jattributes silently breaks forever | FK cascade — rename/delete propagates automatically |
| Multi-value per attribute | Impossible (dict key is unique) | Native M2M on `AssignedProductAttribute.values` |
| Attribute display order | None | `AttributeProduct.sort_order` |
| Value display order | `-id` (newest first) | `AttributeValue.sort_order` (draggable) |
| Filter by attribute | `jattributes__contains` GIN — fragile, no multi-value | `JOIN: attributes__values__slug="gold-22k"` |
| Input type modeling | None | `Attribute.input_type` (DROPDOWN/MULTISELECT/FILE) |
| Visibility/filtering flags | None | `visible_in_storefront`, `filterable_in_dashboard`, etc. |
| Duplicate assignment guard | None | `unique_together (product, assignment)` at DB level |

---

### Phase 1 — Add normalized tables alongside jattributes (schema only)
*jattributes untouched — app keeps working*

1. Add **`AttributeProduct`**: FK `Attribute` + FK `ProductType` + `sort_order`. `unique_together = (attribute, product_type)`.
2. Add **`AttributeVariant`**: same pattern for variant-level.
3. Change `ProductType.product_attributes` M2M → `through=AttributeProduct`. Same related name, so `product_type.product_attributes.all()` still works everywhere.
4. Change `ProductType.variant_attributes` M2M → `through=AttributeVariant`.
5. Add **`AssignedProductAttribute`**: FK `Product` + FK `AttributeProduct` (assignment) + M2M `AttributeValue`. `unique_together = (product, assignment)`.
6. Add **`AssignedVariantAttribute`**: FK `ProductVariant` + FK `AttributeVariant` + M2M `AttributeValue`. `unique_together = (variant, assignment)`.
7. Add `input_type`, `value_required`, `visible_in_storefront`, `filterable_in_storefront`, `filterable_in_dashboard` to `Attribute`.
8. Add `sort_order PositiveIntegerField(null=True)` to `AttributeValue`.
9. **Migration 0006** + `migrate_schemas`.

### Phase 2 — Data migration (jattributes → normalized)
*Depends on Phase 1*

10. Write management command `migrate_jattributes_to_normalized` — reads each `Product.jattributes` dict, resolves `Attribute` by name, `AttributeValue` by name, creates `AttributeProduct` + `AssignedProductAttribute` + value links. Same for `ProductVariant`. Logs skips.
11. Run on a single test tenant first, verify row counts match.

### Phase 3 — Switch application code to read/write normalized tables
*Depends on Phase 2 verified*

12. Rewrite `get_product_attributes_data()` and `get_variant_attributes_data()` in attributes.py to query `AssignedProductAttribute/Variant` (prefetch-friendly, no N+1).
13. Rewrite `AttributesMixin.prepare_fields_for_attributes()` and `get_saved_attributes()` in forms.py to read/write assignment rows instead of `jattributes` dict.
14. Remove `jattributes` writes from `ProductForm.save()` and `ProductVariantForm.save()`.
15. Templates: minimal changes — `get_attributes()` already abstracts the source.

### Phase 4 — Drop jattributes
*Depends on Phase 3 verified end-to-end*

16. Remove `jattributes` from `Product` and `ProductVariant`.
17. **Migration 0007** `RemoveField` x2 + `migrate_schemas`.

---

**Relevant files**
- models/product.py — 4 new models, 2 M2M `through=` changes, fields on `Attribute`/`AttributeValue`
- attributes.py — 3 helpers rewritten in Phase 3
- forms.py — `AttributesMixin` rewritten in Phase 3
- `apps/tenant_apps/product/management/commands/migrate_jattributes_to_normalized.py` — new in Phase 2
- Migrations 0006, 0007

**Verification**
1. Phase 1: `manage.py check` + `migrate_schemas` clean; existing product create/edit still works
2. Phase 2: `AssignedProductAttribute` count == non-empty `jattributes` entries; spot-check 5 products
3. Phase 3: create product with attributes → appears on detail page; edit → updates correctly
4. Phase 4: `manage.py check` clean; no `jattributes` column; all attribute flows work

**Explicit exclusions**
- Not adopting `PublishableModel`, `SeoModel`, `TranslationProxy`, `MoneyField` from new_product.py — separate concerns
- Not implementing `sort_by_attribute()` queryset in Phase 1 — add after full cutover
- new_product.py stays as reference, not imported
- `SortableModel` mixin not pulled in (needs uninstalled packages) — use plain `PositiveIntegerField(null=True)` for sort_order

---

Ready to proceed with Phase 1?