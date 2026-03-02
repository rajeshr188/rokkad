# Contact Model Field Naming Changes

## Summary

Based on your request, the following changes have been made to keep `firstname` and `lastname` as the field names (NOT snake_case `first_name`/`last_name`):

---

## Changes Made

### 1. Customer Model Fields

**BEFORE**:
- `name` - CharField (redundant full name field)
- `firstname` - CharField (separate field)
- `lastname` - CharField (separate field)

**AFTER**:
- `firstname` - CharField (renamed from `name`, max_length=255)
- `lastname` - CharField (kept as is, max_length=255)
- `name` - @property (computed from firstname + lastname)

**Result**: The `name` field has been renamed to `firstname` in the database, and we've kept `lastname`. The duplicate `firstname` field will be handled in the data migration.

---

### 2. Files Updated

#### Models
✅ [apps/tenant_apps/contact/models.py](apps/tenant_apps/contact/models.py)
- Changed `first_name` → `firstname`
- Changed `last_name` → `lastname`
- Updated indexes to use `firstname`, `lastname`
- Updated `name` @property to compute from `firstname` + `lastname`
- Updated `__str__` to use `name` property
- Updated validation in `clean()` method

#### Filters
✅ [apps/tenant_apps/contact/filters.py](apps/tenant_apps/contact/filters.py)
- Updated `universal_search()` to use `firstname__icontains` and `lastname__icontains`

#### Admin
✅ [apps/tenant_apps/contact/admin.py](apps/tenant_apps/contact/admin.py)
- Updated `search_fields` to use `firstname`, `lastname`
- Updated `list_display` to use `name` (which is now a property)

#### Forms
✅ [apps/tenant_apps/contact/forms.py](apps/tenant_apps/contact/forms.py)
- Updated AddressForm: `doorno` → `door_number`, `zipcode` → `zip_code`
- Updated ProofForm: `proof_no` → `proof_number`, `doc` → `document`

#### Girvi App (Related Files)
✅ [apps/tenant_apps/girvi/admin.py](apps/tenant_apps/girvi/admin.py)
- Updated search fields: `customer__firstname`, `customer__lastname`

✅ [apps/tenant_apps/girvi/filters.py](apps/tenant_apps/girvi/filters.py)
- Updated universal search: `customer__firstname`, `customer__lastname`

✅ [apps/tenant_apps/girvi/services.py](apps/tenant_apps/girvi/services.py)
- Updated values clause: `customer__firstname`, `customer__lastname`

✅ [apps/tenant_apps/girvi/views/reports.py](apps/tenant_apps/girvi/views/reports.py)
- Updated all report configs to use `customer__firstname`, `customer__lastname`

---

### 3. Migration File

✅ [apps/tenant_apps/contact/migrations/0002_contact_model_refactoring.py](apps/tenant_apps/contact/migrations/0002_contact_model_refactoring.py)

**Key Operations**:
1. Renames `name` field → `firstname`
2. Updates field definitions
3. Handles all Address, Contact, Proof, CustomerRelationship changes
4. Creates necessary indexes

**Important Note**: Since you have both `name` and `firstname` fields in the database, you should:
- Decide which field contains the correct data
- Create a data migration if needed to merge/copy data before applying this migration
- The current migration assumes `name` field contains the data you want to keep as `firstname`

---

## Field Naming Convention

You've chosen **camelCase** field names:
- `firstname` ✅
- `lastname` ✅  
- `doorno` → `door_number` (snake_case for clarity)
- `zipcode` → `zip_code` (snake_case for clarity)
- `proof_no` → `proof_number` (snake_case for clarity)

This is consistent for the customer name fields while keeping clarity for address/proof fields.

---

## How the `name` Property Works

```python
@property
def name(self):
    """Get customer's full name"""
    if self.lastname:
        return f"{self.firstname} {self.lastname}".strip()
    return self.firstname
```

**Usage in templates/views**:
```python
customer.name  # Returns "John Doe" (computed)
customer.firstname  # Returns "John"
customer.lastname  # Returns "Doe"
```

All existing code using `customer.name` will continue to work!

---

## Database Schema Changes

### Before Migration:
```
customer table:
  - id
  - name (contains full name data)
  - firstname (separate field)
  - lastname
```

### After Migration:
```
customer table:
  - id
  - firstname (renamed from 'name', contains full name data)
  - lastname
```

---

## Next Steps

### 1. Handle Duplicate Data (Important!)

If your current database has data in both `name` AND `firstname` fields, you need to decide:

**Option A**: Keep `name` field data (already in migration)
```python
# The migration already does this:
# Renames 'name' → 'firstname'
```

**Option B**: Keep `firstname` field data (need to modify migration)
```python
# Would need to:
# 1. Copy firstname → name
# 2. Delete old firstname
# 3. Rename name → firstname
```

**Option C**: Merge both fields
```python
# Create a data migration to:
# 1. Decide which field to use (name or firstname)
# 2. Merge/validate data
# 3. Then apply the schema migration
```

### 2. Apply Migration

```bash
# Review what SQL will be executed
.venv\Scripts\python.exe manage.py sqlmigrate contact 0002

# Apply the migration
.venv\Scripts\python.exe manage.py migrate contact

# Verify in shell
.venv\Scripts\python.exe manage.py shell
```

### 3. Test in Shell

```python
from apps.tenant_apps.contact.models import Customer

# Get a customer
customer = Customer.objects.first()

# Test the fields
print(f"firstname: {customer.firstname}")
print(f"lastname: {customer.lastname}")
print(f"name (property): {customer.name}")

# Should output:
# firstname: John
# lastname: Doe  
# name (property): John Doe
```

---

## Benefits

1. ✅ **Simpler field names**: `firstname`, `lastname` (not snake_case)
2. ✅ **No redundancy**: Single source of truth for name data
3. ✅ **Backward compatibility**: `customer.name` still works as a computed property
4. ✅ **Better performance**: No need to keep three fields in sync
5. ✅ **Cleaner code**: One field per piece of data

---

## Database Column Names

The actual database columns will be:
- `firstname` (not `first_name`)
- `lastname` (not `last_name`)

This matches your preference for keeping the database column as `firstname`.

---

## Potential Issues

⚠️ **If you have data in both `name` and `firstname` fields**:
- You need to decide which one to keep
- Create a data migration before applying this schema migration
- Example data migration:

```python
# Create with: python manage.py makemigrations --empty contact

from django.db import migrations

def merge_name_fields(apps, schema_editor):
    Customer = apps.get_model('contact', 'Customer')
    for customer in Customer.objects.all():
        # Decide logic: use 'name' if it exists, else use 'firstname'
        if customer.name:
            customer.firstname = customer.name
        # Or merge them, or use firstname, etc.
        customer.save()

class Migration(migrations.Migration):
    dependencies = [
        ('contact', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(merge_name_fields),
    ]
```

---

## Summary

Your database will now have:
- `firstname` field (from old `name` field)
- `lastname` field (kept as is)
- `customer.name` as a computed property

All references throughout the codebase have been updated to use `firstname`/`lastname`.

The migration is ready to apply once you've confirmed the data handling approach!
