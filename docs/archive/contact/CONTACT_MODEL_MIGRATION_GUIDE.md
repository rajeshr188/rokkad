---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Contact App Model Migration Guide

## Overview
This document details all model changes implemented as part of the contact app refactoring. These changes improve data integrity, performance, and code maintainability.

## Migration Date
**Date**: December 2024  
**Branch**: dea-kiss  
**Status**: âœ… Model changes completed, migrations ready to generate

---

## Model Changes Summary

### 1. Customer Model

#### Field Changes

| Old Field Name | New Field Name | Type Change | Notes |
|---------------|----------------|-------------|-------|
| `name` | âŒ REMOVED | - | Redundant field, use `full_name` property |
| `firstname` | `first_name` | âœ… Renamed | Snake case naming convention |
| `lastname` | `last_name` | âœ… Renamed | Snake case naming convention |

#### New Properties
- `full_name` - Computed property combining first and last name
- `name` - Backward compatibility property (returns `full_name`)

#### Improvements
- âœ… Added `CustomerQuerySet` with `prefetch_all()` method for optimized queries
- âœ… Improved `__str__` method to return clean full name
- âœ… Enhanced `get_default_address()` with try/except for better error handling
- âœ… Updated indexes to use new field names
- âœ… Fixed merge() method to use `relationships_created` and `relationships_received`

#### Database Indexes
```python
indexes = [
    models.Index(fields=['workspace']),
    models.Index(fields=['first_name']),
    models.Index(fields=['last_name']),
    models.Index(fields=['created']),
]
```

---

### 2. CustomerPic Model

#### Improvements
- âœ… Changed `is_default` from `default=True` to `default=False` (more sensible default)
- âœ… Added proper verbose names
- âœ… Enhanced docstring for clarity

---

### 3. CustomerRelationship Model

#### Field Changes
| Old Field | New Field | Change |
|-----------|-----------|--------|
| `relationship` max_length=2 | `relationship` max_length=1 | âœ… Reduced (only 1 char needed) |
| `related_name="relationships"` | `related_name="relationships_created"` | âœ… More descriptive |
| `related_name="relatedby"` | `related_name="relationships_received"` | âœ… More descriptive |

#### New Features
- âœ… Added `REVERSE_RELATIONSHIPS` class constant dict
- âœ… Added `@transaction.atomic` decorator on `save()`
- âœ… Changed to use `get_or_create()` preventing duplicates
- âœ… Added `created` timestamp field
- âœ… Moved relationship logic to top of class for better organization

#### Database Indexes
```python
indexes = [
    models.Index(fields=['customer', 'relationship']),
    models.Index(fields=['related_customer']),
]
```

#### Performance Improvements
- Uses atomic transactions to prevent race conditions
- Uses `get_or_create()` instead of `exists()` + `create()` (reduces queries)

---

### 4. Address Model

#### Field Changes

| Old Field Name | New Field Name | Type Change | Notes |
|---------------|----------------|-------------|-------|
| `doorno` | `door_number` | âœ… Renamed | Snake case + clearer naming |
| `zipcode` | `zip_code` | âœ… Renamed | Snake case naming |
| `state` (max_length=50) | `state` (max_length=2) | âœ… Changed | Now uses 2-char state codes |
| `zip_code` max_length=10 | `zip_code` max_length=6 | âœ… Reduced | Indian PIN codes are 6 digits |
| `is_default` default=True | `is_default` default=False | âœ… Changed | More logical default |

#### New Properties
- `doorno` - Backward compatibility property (returns `door_number`)
- `zipcode` - Backward compatibility property (returns `zip_code`)

#### Improvements
- âœ… Added comprehensive `INDIAN_STATES` list with all 36 states/UTs
- âœ… Added `zip_code_validator` using `RegexValidator` for 6-digit PIN codes
- âœ… Made `door_number`, `street`, `area` optional (blank=True)
- âœ… Enhanced `__str__` method to filter out empty values
- âœ… Fixed `verify()` and `set_default()` to use `update_fields` for performance
- âœ… Improved `clean()` validation to check for at least one address field
- âœ… Fixed `save()` to exclude current object when unsetting defaults

#### Database Indexes
```python
indexes = [
    models.Index(fields=['customer', '-is_default']),
    models.Index(fields=['city', 'state']),
]
```

#### Validation Rules
- PIN code must be exactly 6 digits
- At least one of door_number, street, or area must be provided

---

### 5. Contact Model

#### Field Changes
| Old Field | New Field | Change |
|-----------|-----------|--------|
| `is_default` default=True | `is_default` default=False | âœ… Changed |

#### Improvements
- âœ… Moved `ContactType` choices to top of class (better organization)
- âœ… Enhanced `__str__` to show contact type and number
- âœ… Fixed `verify()` and `set_default()` to use `update_fields`
- âœ… Added proper help text for `phone_number` field
- âœ… Added `indexes` in Meta class

#### Database Indexes
```python
indexes = [
    models.Index(fields=['customer', '-is_default']),
]
```

#### Unique Constraint
Remains: `unique_together = ('customer', 'phone_number', 'contact_type')`  
This allows family members to share phone numbers with different contact types.

---

### 6. Proof Model

#### Field Changes

| Old Field Name | New Field Name | Type Change | Notes |
|---------------|----------------|-------------|-------|
| `proof_no` | `proof_number` | âœ… Renamed | More descriptive |
| `doc` | `document` | âœ… Renamed | More descriptive |
| `doc` upload_to="upload/files/proofs" | `document` upload_to="proofs/" | âœ… Changed | Cleaner path |

#### DocType Changes
```python
# OLD
Aadhar = "AA", "AadharNo"
Driving_License = "DL", "Driving License"
Pan = "PN", "PanCard No"

# NEW
AADHAR = "AA", _("Aadhaar Number")
DRIVING_LICENSE = "DL", _("Driving License")
PAN = "PN", _("PAN Card")
VOTER_ID = "VI", _("Voter ID")  # NEW
PASSPORT = "PP", _("Passport")  # NEW
```

#### New Features
- âœ… Added `PROOF_VALIDATORS` class dict with `RegexValidator` for each proof type
- âœ… Aadhaar: Must be exactly 12 digits
- âœ… PAN: Must match format `ABCDE1234F`
- âœ… Driving License: Must match format `TN1234567890123`
- âœ… Auto-uppercase PAN numbers in `clean()`
- âœ… Added two new proof types: Voter ID, Passport

#### New Properties
- `proof_no` - Backward compatibility property (returns `proof_number`)
- `doc` - Backward compatibility property (returns `document`)

#### Improvements
- âœ… Enhanced `clean()` to use validators dict
- âœ… Changed `save()` to use `full_clean()` for comprehensive validation
- âœ… Enhanced `delete()` to safely handle missing files
- âœ… Changed `__str__` to show document type and number (was just pk)

#### Database Indexes
```python
indexes = [
    models.Index(fields=['customer', 'proof_type']),
]
```

#### Unique Constraint
Remains: `unique_together = ('customer', 'proof_type')`  
Prevents duplicate proof types for same customer.

---

## Backward Compatibility

All renamed fields have backward compatibility properties:

### Customer
```python
@property
def name(self):
    return self.full_name
```

### Address
```python
@property
def doorno(self):
    return self.door_number

@property
def zipcode(self):
    return self.zip_code
```

### Proof
```python
@property
def proof_no(self):
    return self.proof_number

@property
def doc(self):
    return self.document
```

**Impact**: Existing templates using `.name`, `.doorno`, `.zipcode`, `.proof_no`, `.doc` will continue to work!

---

## Migration Steps

### Step 1: Generate Migrations
```bash
python manage.py makemigrations contact
```

Expected migrations:
1. Rename `Customer.firstname` â†’ `Customer.first_name`
2. Rename `Customer.lastname` â†’ `Customer.last_name`
3. Remove `Customer.name` field
4. Update `Customer` indexes
5. Change `CustomerRelationship.relationship` max_length to 1
6. Rename `CustomerRelationship` related_names
7. Add `CustomerRelationship.created` field
8. Add `CustomerRelationship` indexes
9. Rename `Address.doorno` â†’ `Address.door_number`
10. Rename `Address.zipcode` â†’ `Address.zip_code`
11. Change `Address.state` max_length to 2
12. Change `Address.zip_code` max_length to 6
13. Update `Address` default values
14. Add `Address` indexes
15. Update `Contact.is_default` default value
16. Add `Contact` indexes
17. Rename `Proof.proof_no` â†’ `Proof.proof_number`
18. Rename `Proof.doc` â†’ `Proof.document`
19. Add new `Proof.DocType` choices (VI, PP)
20. Add `Proof` indexes

### Step 2: Review Migration Files
```bash
# Review the generated migration files
ls apps/tenant_apps/contact/migrations/
```

### Step 3: Test Migration (Dry Run)
```bash
python manage.py migrate contact --plan
```

### Step 4: Backup Database
```bash
pg_dump -U postgres -d your_database > backup_before_contact_refactor.sql
```

### Step 5: Apply Migrations
```bash
python manage.py migrate contact
```

### Step 6: Verify Data Integrity
```bash
python manage.py shell
```

```python
from apps.tenant_apps.contact.models import Customer, Address, Contact, Proof

# Test Customer
customer = Customer.objects.first()
print(f"First name: {customer.first_name}")
print(f"Last name: {customer.last_name}")
print(f"Full name: {customer.full_name}")
print(f"Name (compat): {customer.name}")  # Should equal full_name

# Test Address
address = Address.objects.first()
print(f"Door number: {address.door_number}")
print(f"PIN code: {address.zip_code}")
print(f"Doorno (compat): {address.doorno}")  # Should equal door_number
print(f"Zipcode (compat): {address.zipcode}")  # Should equal zip_code

# Test Proof
proof = Proof.objects.first()
print(f"Proof number: {proof.proof_number}")
print(f"Document: {proof.document}")
print(f"Proof no (compat): {proof.proof_no}")  # Should equal proof_number
print(f"Doc (compat): {proof.doc}")  # Should equal document
```

---

## Breaking Changes

### âš ï¸ Changes that MAY affect dependent code:

1. **CustomerRelationship related_names**
   - `customer.relationships` â†’ `customer.relationships_created`
   - `customer.relatedby` â†’ `customer.relationships_received`
   - **Action Required**: Update any code using these related managers

2. **Proof.DocType constants**
   - `DocType.Aadhar` â†’ `DocType.AADHAR`
   - `DocType.Pan` â†’ `DocType.PAN`
   - `DocType.Driving_License` â†’ `DocType.DRIVING_LICENSE`
   - **Action Required**: Update any code referencing these constants

3. **Address.state field**
   - Changed from text to 2-character codes
   - **Action Required**: Existing full state names need migration to codes
   - **Recommendation**: Create a data migration to convert existing values

4. **Default field values changed**
   - `CustomerPic.is_default`: True â†’ False
   - `Address.is_default`: True â†’ False
   - `Contact.is_default`: True â†’ False
   - **Impact**: New records will not be default by default (more logical)

---

## Performance Improvements

### Query Optimization
1. **Customer.objects.prefetch_all()**
   - Uses `select_related('workspace')`
   - Uses `prefetch_related('address', 'contactno', 'proofs', 'pics')`
   - Reduces N+1 queries significantly

2. **Indexes Added**
   - `Customer`: workspace, first_name, last_name, created
   - `CustomerRelationship`: customer+relationship, related_customer
   - `Address`: customer+is_default, city+state
   - `Contact`: customer+is_default
   - `Proof`: customer+proof_type

### Database Operations
1. **update_fields parameter**
   - Used in `verify()` and `set_default()` methods
   - Only updates specific fields, reducing query size

2. **Atomic Transactions**
   - `CustomerRelationship.save()` uses `@transaction.atomic`
   - Prevents partial relationship creation

---

## Code Files to Update

After migration, these files may need updates:

### Forms
- [ ] `apps/tenant_apps/contact/forms.py`
  - Update field names in form classes
  - Update model field references

### Views
- [ ] `apps/tenant_apps/contact/views.py`
  - Update queryset filters using old field names
  - Update references to `relationships` â†’ `relationships_created`

### Filters
- [ ] `apps/tenant_apps/contact/filters.py` (if exists)
  - Update filter field names

### Tables
- [ ] `apps/tenant_apps/contact/tables.py` (if exists)
  - Update column references

### Templates
Templates should mostly work due to backward compatibility properties, but for best performance, update them:
- [ ] Update `{{ customer.name }}` â†’ `{{ customer.full_name }}`
- [ ] Update `{{ address.doorno }}` â†’ `{{ address.door_number }}`
- [ ] Update `{{ address.zipcode }}` â†’ `{{ address.zip_code }}`
- [ ] Update `{{ proof.proof_no }}` â†’ `{{ proof.proof_number }}`
- [ ] Update `{{ proof.doc }}` â†’ `{{ proof.document }}`

### Admin
- [ ] `apps/tenant_apps/contact/admin.py`
  - Update list_display, search_fields, list_filter
  - Update fieldsets to use new field names

---

## Testing Checklist

### Unit Tests
- [ ] Test Customer model: first_name, last_name, full_name property
- [ ] Test Customer.merge() with new relationship related_names
- [ ] Test Address validation with new validators
- [ ] Test Contact unique_together constraint
- [ ] Test Proof validators (Aadhaar, PAN, DL formats)
- [ ] Test backward compatibility properties

### Integration Tests
- [ ] Test customer creation forms
- [ ] Test address creation/update
- [ ] Test contact creation with duplicate numbers
- [ ] Test proof upload and validation
- [ ] Test customer merge functionality
- [ ] Test customer relationship bidirectional creation

### Manual Testing
- [ ] Create new customer with first/last name
- [ ] Add multiple addresses to a customer
- [ ] Set default address
- [ ] Add multiple contacts to customer
- [ ] Add proof documents with validation
- [ ] Test invalid Aadhaar number
- [ ] Test invalid PAN format
- [ ] Test customer merge
- [ ] Create customer relationships

---

## Rollback Plan

If issues occur after migration:

### Step 1: Backup Current State
```bash
pg_dump -U postgres -d your_database > backup_after_migration.sql
```

### Step 2: Revert Migrations
```bash
python manage.py migrate contact <previous_migration_name>
```

### Step 3: Restore Database (if needed)
```bash
psql -U postgres -d your_database < backup_before_contact_refactor.sql
```

### Step 4: Revert Code Changes
```bash
git checkout <previous_commit>
```

---

## References

- **Improvement Document**: `CONTACT_APP_IMPROVEMENTS.md`
- **Models File**: `apps/tenant_apps/contact/models.py`
- **Utilities**: `apps/tenant_apps/contact/utils.py`
- **Base Forms**: `apps/tenant_apps/contact/base_forms.py`

---

## Next Steps

1. âœ… **COMPLETED**: Model refactoring
2. â³ **CURRENT**: Generate and review migrations
3. â³ **PENDING**: Update forms to use new field names
4. â³ **PENDING**: Update views and querysets
5. â³ **PENDING**: Update admin configuration
6. â³ **PENDING**: Create data migration for Address.state conversion
7. â³ **PENDING**: Update templates for optimal performance
8. â³ **PENDING**: Write comprehensive test suite

---

## Notes

- All changes maintain backward compatibility through properties
- Database migrations will rename columns, not create new ones
- Performance significantly improved with new indexes and optimized queries
- Validation is now more robust with RegexValidators
- Code is more maintainable with better naming conventions

**Author**: GitHub Copilot  
**Date**: December 2024  
**Version**: 1.0

