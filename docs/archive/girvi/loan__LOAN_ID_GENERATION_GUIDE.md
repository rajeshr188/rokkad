---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Simplified Loan ID Generation System

## Overview

The loan ID generation system uses a **clean, mandatory series approach** with globally unique formatted IDs.

**Key Principle**: Every loan must belong to a series. The loan_id is a formatted string like `"A00123"` that is globally unique across the entire system.

## Architecture

### Core Components

1. **`BaseLoan.loan_id`** - `CharField` storing formatted ID (e.g., "A00123")
2. **`BaseLoan.series`** - **Required** FK, every loan must have a series
3. **`BaseLoan.license`** - Property that returns `series.license`
4. **`LoanIDGenerator`** - Simple service class for generation

### Why This Is Better

âœ… **Globally Unique** - No ambiguity, "A00123" is unique across all loans  
âœ… **Simple Model** - One FK (series), no complex constraints  
âœ… **Natural Sorting** - Alphabetical sorting works perfectly  
âœ… **Clear Communication** - "Loan A00123" is unambiguous  
âœ… **Audit-Friendly** - Every reference is unique

## Database Schema

```python
class BaseLoan(BusinessDoc):
    loan_id = models.CharField(
        max_length=50,
        unique=True,  # Globally unique!
        db_index=True
    )
    
    series = models.ForeignKey(
        "girvi.Series",
        on_delete=models.PROTECT  # Required - can't delete series with loans
    )
    
    @property
    def license(self):
        return self.series.license
```

## Usage

### Scenario 1: Normal Loan Creation (Legacy Users)

**Use Case**: User with existing series books (A, B, C...)

```python
series_a = Series.objects.get(prefix='A')

loan = GivenLoan(
    series=series_a,
    customer=customer,
    loan_date=timezone.now()
)
loan.save()

# Results:
# loan.loan_id = "A01234" (globally unique string)
# loan.series = Series(A)
# loan.license = series_a.license (via property)
```

### Scenario 2: New User (No Existing Series)

**Use Case**: New user starting fresh

```python
# Step 1: Create a default series for the license
license = License.objects.first()
default_series = Series.objects.create(
    license=license,
    prefix='L1',  # License-based prefix
    name='Default',
    max_limit=6,  # Up to 999,999 loans
    is_active=True
)

# Step 2: Create loans normally
loan = GivenLoan(
    series=default_series,
    customer=customer
)
loan.save()

# Results:
# loan.loan_id = "L1000001" (globally unique)
```

### Scenario 3: Manual Import with Custom ID

**Use Case**: Importing legacy data with specific loan IDs

```python
series_b = Series.objects.get(prefix='B')

# You can manually set loan_id before save
loan = GivenLoan(
    series=series_b,
    customer=customer
)
loan.loan_id = "B12345"  # Manually set for import
loan.save()

# Results:
# loan.loan_id = "B12345" (preserved as-is)
```

**Warning**: When manually setting loan_id, ensure it doesn't conflict with existing IDs and follows series prefix format.

## Generation Logic

### How It Works

```python
# In LoanIDGenerator.generate(series)
with transaction.atomic():
    # 1. Lock series row (prevents race conditions)
    series = Series.objects.select_for_update().get(id=series.id)
    
    # 2. Get last loan in series
    last_loan = series.loan_set.order_by("-loan_id").first()
    
    # 3. Extract number from formatted ID
    if last_loan:
        last_num = int(last_loan.loan_id[len(series.prefix):])  # "A00123" -> 123
        next_num = last_num + 1  # 124
    else:
        next_num = 1
    
    # 4. Format with prefix and padding
    return f"{series.prefix}{next_num:0{series.max_limit}d}"  # "A00124"
```

### Thread Safety

- Uses `select_for_update()` to lock the series row
- Prevents concurrent loans from getting the same ID
- Transaction-safe

## Setting Up New Users

For users who don't need multiple series:

```python
def create_default_series_for_license(license):
    """Auto-create a default series for simplified users"""
    return Series.objects.get_or_create(
        license=license,
        prefix=f'L{license.id}',  # e.g., L1, L2, L3
        defaults={
            'name': 'Default',
            'max_limit': 6,
            'is_active': True
        }
    )[0]

# Usage in views/signals:
license = request.user.profile.default_license
series = create_default_series_for_license(license)
loan = GivenLoan(series=series, customer=customer)
loan.save()
```

## API Reference

### `LoanIDGenerator.generate(series)`

```python
from apps.tenant_apps.girvi.services import LoanIDGenerator

# Generate next loan ID for a series
loan_id = LoanIDGenerator.generate(series)
# Returns: "A00124" (formatted string, ready to use)

# Example:
series_a = Series.objects.get(prefix='A')
new_loan_id = LoanIDGenerator.generate(series_a)
loan = GivenLoan(series=series_a, loan_id=new_loan_id, customer=customer)
loan.save()
```

### `Series.format_loan_id(number)`

```python
series = Series.objects.get(prefix='A', max_limit=5)
formatted = series.format_loan_id(123)
# Returns: "A00123"
```

### `BaseLoan.save()`

Auto-generates loan_id if not set:

```python
loan = GivenLoan(series=my_series, customer=customer)
# loan_id is None

loan.save()
# loan_id is auto-generated: "A00124"
```

## Migration Strategy

### Migrating from Old System

If you have existing loans with different structure:

```python
# Old: Integer-based with optional series
# New: String-based with mandatory series

for old_loan in OldLoan.objects.all():
    # Ensure series exists
    if not old_loan.series:
        # Create default series for this license
        series = create_default_series_for_license(old_loan.license)
    else:
        series = old_loan.series
    
    # Format old loan_id if needed
    if isinstance(old_loan.loan_id, int):
        new_loan_id = series.format_loan_id(old_loan.loan_id)
    else:
        new_loan_id = old_loan.loan_id
    
    # Create new loan
    new_loan = GivenLoan(
        loan_id=new_loan_id,
        series=series,
        customer=old_loan.customer,
        # ... other fields
    )
    new_loan.save()
```

## View Integration

### Form Initialization

```python
def _get_initial_loan_data(request, customer_pk=None):
    """Get initial data for new loan form"""
    
    # Get user's last-used series or create default
    try:
        latest_loan = Loan.objects.select_related("series").latest("id")
        series = latest_loan.series
    except Loan.DoesNotExist:
        # Create/get default series
        license = request.user.profile.default_license
        series = create_default_series_for_license(license)
    
    initial = {
        'series': series,
        'loan_date': get_default_date(request),
    }
    
    if customer_pk:
        initial['customer'] = get_object_or_404(Customer, pk=customer_pk)
    
    return initial
```

### Form Display

In templates, just use `loan.loan_id` - it's already formatted!

```html
<div class="loan-header">
    <h2>Loan {{ loan.loan_id }}</h2>  <!-- Shows: Loan A00123 -->
    <p>License: {{ loan.license.name }}</p>
    <p>Series: {{ loan.series.name }}</p>
</div>
```

## Comparison: Old vs New

| Aspect | Old (Complex) | **New (Simple)** |
|--------|--------------|------------------|
| **loan_id Type** | Integer | **String (formatted)** âœ… |
| **Series** | Optional | **Required** âœ… |
| **License FK** | Direct | **Via series** âœ… |
| **reference_id** | Separate field | **Not needed** âœ… |
| **Uniqueness** | Per-series/license | **Global** âœ… |
| **Constraints** | Complex UniqueConstraint | **Simple unique=True** âœ… |
| **Sorting** | Needs context | **Natural alphabetical** âœ… |
| **Display** | Needs formatting | **Already formatted** âœ… |

## Best Practices

1. âœ… **Always provide series** when creating loans
2. âœ… **Let save() auto-generate** loan_id (don't manually set unless importing)
3. âœ… **Use PROTECT on_delete** for series FK (prevent accidental deletion)
4. âœ… **Create default series** for new users who don't need multiple books
5. âœ… **Use loan.loan_id directly** in UI (no formatting needed)

## Troubleshooting

### Error: "Series is required to create a loan"

**Cause**: Trying to create loan without series

**Solution**:
```python
# Before:
loan = GivenLoan(customer=customer)  # âŒ No series

# After:
series = Series.objects.filter(is_active=True).first()
loan = GivenLoan(series=series, customer=customer)  # âœ…
```

### Error: Duplicate key violation on loan_id

**Cause**: Manually setting loan_id that already exists

**Solution**:
```python
# Don't manually set loan_id unless importing
loan = GivenLoan(series=series, customer=customer)
# loan.loan_id = "A00123"  # âŒ Don't do this
loan.save()  # âœ… Auto-generates unique ID
```

### Series Prefix: How to Choose?

```python
# For existing users with physical books:
Series(prefix='A', name='Book A')  # Match physical book labels

# For new users:
Series(prefix=f'L{license.id}', name='Default')  # L1, L2, L3...

# For different loan types:
Series(prefix='G', name='Given Loans')  # Gold loans
Series(prefix='S', name='Silver Loans')  # Silver loans
```

## Performance Considerations

- `select_for_update()` creates row locks - keep transactions short
- Index on `loan_id` (already unique) for fast lookups
- Index on `series` FK for filtering
- Natural alphabetical ordering is efficient

## Summary

The new system is **dramatically simpler**:
- One FK (series) instead of two (series + license)
- No reference_id field
- No complex constraints
- loan_id is the formatted string you want to display
- Globally unique, sortable, clear

**Result**: Less code, fewer bugs, easier to understand and maintain!

### Key Components

1. **`BaseLoan.loan_id`** - `PositiveIntegerField` storing the sequence number
2. **`BaseLoan.license`** - Required FK, every loan belongs to a license
3. **`BaseLoan.series`** - Optional FK, for series-based loans
4. **`BaseLoan.reference_id`** - Optional CharField for manual/legacy IDs
5. **`LoanIDGenerator`** - Unified service class in `services.py`

### Database Constraints

```python
# Unique per series (when series exists)
UniqueConstraint(
    fields=['series', 'loan_id'],
    condition=Q(series__isnull=False)
)

# Unique per license (when no series)
UniqueConstraint(
    fields=['license', 'loan_id'],
    condition=Q(series__isnull=True)
)
```

## Usage Scenarios

### Scenario 1: Series-Based Loan (Legacy Users)

**Use Case**: User has license with multiple series (A, B, C...), each with ~10,000 loan capacity.

```python
license = License.objects.get(id=1)
series = Series.objects.get(license=license, prefix='A')

# Create loan - loan_id auto-generated
loan = GivenLoan(
    license=license,
    series=series,
    customer=customer,
    loan_date=timezone.now()
)
loan.save()

# Results:
# loan.loan_id = 1234 (integer)
# loan.series = Series(A)
# loan.display_id = "A01234" (formatted with prefix)
```

**Sequence Logic**:
- Gets max `loan_id` from loans WHERE `series_id = A`
- Increments by 1
- Thread-safe with `select_for_update()`

### Scenario 2: License-Only Loan (New Users)

**Use Case**: New user doesn't need series complexity, just simple sequential IDs.

```python
license = License.objects.get(id=2)

# Create loan without series
loan = GivenLoan(
    license=license,
    series=None,  # No series
    customer=customer,
    loan_date=timezone.now()
)
loan.save()

# Results:
# loan.loan_id = 42 (integer)
# loan.series = None
# loan.display_id = "0042" (4-digit padded)
```

**Sequence Logic**:
- Gets max `loan_id` from loans WHERE `license_id = 2 AND series IS NULL`
- Increments by 1
- Separate sequence from series-based loans

### Scenario 3: Reference ID (Manual/Import)

**Use Case**: Importing legacy loans or manually entering old loan books.

#### 3a: Reference ID with Series Pattern

```python
license = License.objects.get(id=1)

# User enters reference_id from old system
loan = GivenLoan(
    license=license,
    reference_id="XY12345",  # Old loan ID
    customer=customer
)
loan.save()

# System automatically:
# 1. Parses "XY" prefix and "12345" number
# 2. Finds or creates Series(prefix='XY')
# 3. Sets loan.loan_id = 12345
# 4. Sets loan.series = Series(XY)
#
# Results:
# loan.loan_id = 12345
# loan.series = Series(XY) [auto-created if needed]
# loan.reference_id = "XY12345"
# loan.display_id = "XY12345 (Ref)"
```

#### 3b: Reference ID without Pattern

```python
# Plain number reference
loan = GivenLoan(
    license=license,
    reference_id="9876",
    customer=customer
)
loan.save()

# Results:
# loan.loan_id = 9876
# loan.series = None
# loan.reference_id = "9876"
# loan.display_id = "9876 (Ref)"
```

## Thread Safety

All sequence generation uses `select_for_update()` to prevent race conditions:

```python
# In Series.get_next_loan_id()
with transaction.atomic():
    series = Series.objects.select_for_update().get(id=self.id)
    last_loan = series.loan_set.filter(series=series).order_by("-loan_id").first()
    return (last_loan.loan_id + 1) if last_loan else 1

# In License.get_next_loan_id_for_license()
with transaction.atomic():
    license = License.objects.select_for_update().get(id=self.id)
    last_loan = Loan.objects.filter(
        license=license, 
        series__isnull=True
    ).order_by("-loan_id").first()
    return (last_loan.loan_id + 1) if last_loan else 1
```

## API Reference

### `LoanIDGenerator.generate()`

```python
def generate(
    license: License,
    series: Optional[Series] = None,
    reference_id: Optional[str] = None
) -> Tuple[int, Optional[Series], Optional[str]]:
    """
    Returns: (loan_id_number, series, reference_id)
    """
```

**Examples**:

```python
from apps.tenant_apps.girvi.services import LoanIDGenerator

# Series-based
loan_id, series, ref = LoanIDGenerator.generate(license, series=my_series)
# -> (1235, Series(A), None)

# License-only
loan_id, series, ref = LoanIDGenerator.generate(license)
# -> (43, None, None)

# Reference ID
loan_id, series, ref = LoanIDGenerator.generate(license, reference_id="B00999")
# -> (999, Series(B), "B00999")
```

### `LoanIDGenerator.format_display_id()`

```python
def format_display_id(
    loan_id: int,
    series: Optional[Series] = None,
    reference_id: Optional[str] = None
) -> str:
```

**Examples**:

```python
# Series loan
LoanIDGenerator.format_display_id(1234, series=Series(prefix='A', max_limit=5))
# -> "A01234"

# License loan
LoanIDGenerator.format_display_id(42, series=None)
# -> "0042"

# Reference loan
LoanIDGenerator.format_display_id(999, series=Series(B), reference_id="B00999")
# -> "B00999 (Ref)"
```

## Migration Strategy

### For Existing Loans

```python
# Old loan model had CharField loan_id like "A00123"
# New model has integer loan_id + series + reference_id

# Migration pseudo-code:
for old_loan in OldLoan.objects.all():
    # Parse old loan_id
    match = re.match(r'^([A-Z]+)(\d+)$', old_loan.loan_id)
    
    if match:
        prefix = match.group(1)
        number = int(match.group(2))
        
        # Find series
        series = Series.objects.get(prefix=prefix, license=old_loan.license)
        
        # Create new loan
        new_loan = GivenLoan(
            loan_id=number,
            series=series,
            license=old_loan.license,
            reference_id=old_loan.loan_id,  # Keep original as reference
            # ... other fields
        )
        new_loan.save()
```

### Adding License Field to Existing Loans

If you have existing loans without license field:

```python
# Populate from series
for loan in Loan.objects.filter(license__isnull=True):
    if loan.series:
        loan.license = loan.series.license
        loan.save(update_fields=['license'])
```

## View/Form Integration

### Creating New Loan Form

```python
# In loan_save view
def _get_initial_loan_data(request, customer_pk=None):
    """Get initial data for new loan form"""
    
    # Get user's preferred license
    license = request.user.profile.default_license
    
    # Try to get last used series
    last_loan = Loan.objects.filter(series__isnull=False).latest('id')
    
    initial = {
        'license': license,
        'loan_date': get_default_date(request),
    }
    
    if last_loan and last_loan.series:
        # Pre-populate with last series (user can change)
        initial['series'] = last_loan.series
    
    return initial
```

### Form Validation

```python
class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['license', 'series', 'reference_id', 'customer', ...]
    
    def clean(self):
        cleaned_data = super().clean()
        license = cleaned_data.get('license')
        series = cleaned_data.get('series')
        
        # Validate series belongs to license
        if series and series.license != license:
            raise ValidationError(
                f"Series {series} does not belong to license {license}"
            )
        
        return cleaned_data
```

## Best Practices

1. **Always provide license** - It's required for sequence integrity
2. **Use series for organization** - Legacy users should continue using series
3. **Reference IDs for imports** - Use when migrating from old systems
4. **Don't manually set loan_id** - Let the system generate it
5. **Use display_id for UI** - Never show raw loan_id to users

## Troubleshooting

### Duplicate Key Error

```
IntegrityError: duplicate key value violates unique constraint 
"girvi_givenloan_unique_loan_per_series"
```

**Cause**: Race condition or manual loan_id assignment

**Solution**: Remove manual loan_id assignment, let save() method generate it

### Wrong Sequence Numbers

**Symptom**: New loan has loan_id=1 but series already has loans

**Causes**:
1. Series filter not working (check series FK is set correctly)
2. Transaction not committed from previous loan creation
3. Using wrong series/license

**Debug**:
```python
# Check last loan in series
Series.objects.get(id=X).loan_set.order_by('-loan_id').first()

# Check last loan in license (no series)
Loan.objects.filter(license_id=Y, series__isnull=True).order_by('-loan_id').first()
```

### Series Auto-Creation Issues

**Symptom**: New series created when importing reference IDs

**Expected behavior**: This is intentional - reference IDs like "XY12345" will auto-create Series(prefix='XY')

**To prevent**: Manually create all expected series before importing

## Performance Considerations

- `select_for_update()` creates row locks - keep transactions short
- Indexes on `(license, loan_id)` and `(series, loan_id)` for fast lookups
- Consider caching last loan_id in Redis for very high-volume scenarios

## Future Enhancements

- [ ] Redis-based sequence cache for ultra-high concurrency
- [ ] Bulk loan creation optimization
- [ ] Series auto-switching at max_limit threshold
- [ ] Multi-format reference ID parsers (non-PREFIX+NUMBER patterns)

