I’ll map the real current user flow from routes → views → forms → templates first, then compare it against a corrected/enhanced flow proposal tied to the new normalized attribute architecture.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/producttype.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/urls.py#1-1), lines 1 to 260

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/product.py)

I have the route backbone; next I’ll extract the create/edit/detail flows from category, variant, and form/template files so we can compare current behavior to the desired architecture-aligned flow.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/forms.py#1-1), lines 1 to 320

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/product/product_form.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/product/generate_pandv.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/product/producttype_form.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/productvariant.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/category.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/product/product_list.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/product/productvariant_list.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/product/productvariant_form.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/product/producttype_detail.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/product/producttype_list.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/filters.py)

Searched for regex `class ProductVariant|track_inventory|def get_bal|display_product|class ProductType\(|name = models.CharField\(max_length=128\)` (`**/apps/tenant_apps/product/models/product.py`), 6 results

I’ve identified a few likely user-flow blockers; I’m quickly verifying one critical one (variant creation path) so the recommendations are grounded in runtime behavior, not just code reading.

Ran terminal command: .venv314\Scripts\python.exe manage.py shell -c "from apps.tenant_apps.product.models import ProductVariant; print('track_inventory' in [f.name for f in ProductVariant._meta.get_fields()]);
try:
    ProductVariant(track_inventory=True)
    print('init_ok')
except Exception as e:
    print(type(e).__name__, e)"

Searched for regex `producttype/<int:pk>/update//|producttype_delete|category_delete|ProductVariant\(product=product, track_inventory=track_inventory\)|variant_form|ProductImageForm|fields = \["alt"\]|Category\.objects\.first\(|productvariant_list|attributes = django_filters.ModelMultipleChoiceFilter|fields = \["product"\]` (`**/apps/tenant_apps/product/**/*.{py,html}`), 36 results

Searched for regex `Generate Products|create product of this type|product_productvariant_create|Delete` (`**/templates/product/**/*.html`), 23 results

Great point. With the architecture migration finished, this is the right time to align product user flow with the new model.

**Current Flow (As Implemented)**
1. Master data setup:
- Category CRUD in category.py
- Attribute and AttributeValue CRUD via routes in urls.py

2. Product type setup:
- ProductType create/update with product and variant attributes in forms.py
- ProductType detail entry points:
  - Generate products: producttype_detail.html
  - Create product manually: producttype_detail.html

3. Product and variant operations:
- Product create/edit in product.py
- Variant create/edit in productvariant.py
- Attribute save/read now normalized through forms/helpers:
  - forms.py
  - attributes.py

4. Bulk generation:
- ProductType-based cartesian generator in producttype.py

**What’s Mismatched or Needs Correction**
1. Critical blocker:
- Product create path uses a non-existent ProductVariant field track_inventory, which causes runtime TypeError for that flow.
- Evidence: product.py

2. Product form flow inconsistency:
- View passes variant_form, but template only renders product_form.
- Evidence:
  - View context: product.py
  - Template: product_form.html

3. Route typo:
- ProductType update path has double slash.
- Evidence: urls.py

4. Unsafe delete flow:
- Category and ProductType deletes are direct function deletes via GET endpoint pattern.
- Evidence:
  - category.py
  - producttype.py

5. Product image create flow likely broken:
- ProductImageForm exposes only alt, not image.
- Evidence: forms.py

6. Variant filter mismatch with normalized model:
- Filter defines attributes, but Meta fields exclude it and no normalized relation filter logic is present.
- Evidence: filters.py

7. Generator category selection is implicit:
- Uses first category silently.
- Evidence: producttype.py

**Recommended User Flow (Architecture-Aligned)**
1. Define ProductType:
- Choose has_variants.
- Select product attributes and variant attributes.

2. Create Product:
- Select category and fill product-level attributes only.

3. Create Variant(s):
- Fill sku, product_code, name, variant-level attributes.
- Repeat for multiple variants when has_variants is true.

4. Optional bulk generate:
- Must require explicit category and optional naming pattern before generation.

5. Manage images:
- Product image upload should require image file.
- Variant image association should be available after variant creation.

6. Discoverability:
- Product and variant list filters should support normalized attribute filtering.

**Next Logical Steps (Enhance/Correct Plan)**
1. Fix flow blockers first:
- Remove or reintroduce track_inventory consistently.
- Render variant_form in product_form template when needed.
- Fix double-slash route.
- Convert category/producttype deletes to POST-confirm flow.

2. Fix operational UX:
- ProductImageForm should include image.
- Generator should require category input, not Category.objects.first().

3. Improve normalized flow usability:
- Add normalized attribute filters to variant list query.
- Expose sku and product_code in variant create/update forms.

4. Hardening:
- Add integration tests for product create/edit and bulk generator UI paths on tenant schema.

If you want, I can implement this in that exact order starting with the blocker bundle (track_inventory + variant_form rendering + route typo + delete safety).