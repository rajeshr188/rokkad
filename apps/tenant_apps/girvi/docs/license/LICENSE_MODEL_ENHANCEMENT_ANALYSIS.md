# License Model Enhancement Analysis & Implementation Plan

## Current State Analysis

### Existing License Model
The current License model has the following characteristics:

**Fields:**
- `name` - License identifier (CharField)
- `type` - License type (choices: PBL, GST)
- `shopname` - Business shop name
- `address` - Business address
- `phonenumber` - Contact number
- `propreitor` - Business owner name
- `renewal_date` - License renewal date

**Limitations:**
1. **No workspace association** - Not connected to Company/Workspace, limiting multi-tenant isolation
2. **Limited license types** - Only PBL (Pawn Brokers License) and GST supported
3. **No expiry tracking** - Only renewal_date, no status management for expired licenses
4. **No document storage** - Cannot store license certificates/documents
5. **Missing business categories** - Cannot mark as pawnbroker-only vs jeweller vs both
6. **No license authority tracking** - No info on issuing authority/license number
7. **Basic business info** - Missing critical fields like email, business type, statutory IDs

### Related Models

**Series Model:**
- Stores loan ID sequences under a license
- Has many-to-one relationship with License
- Used for loan tracking with prefix-based ID generation

**Current Views:**
- List, Create, Detail, Update, Delete for License
- No workspace filtering
- No multi-license comparison

## Enhancement Plan

### 1. Enhanced License Model Structure

#### New Fields to Add:
```python
# Workspace & Authority
- workspace (ForeignKey to Company) - Multi-tenant support
- license_number (CharField) - Unique license identifier from authority
- issuing_authority (CharField) - Authority that issued the license

# License Details
- status (CharField) - Choice: ACTIVE, INACTIVE, EXPIRED, SUSPENDED, PENDING
- date_issued (DateField) - When license was issued
- date_expires (DateField) - When license will expire
- is_renewable (BooleanField) - Whether license auto-renews

# Business Categories
BUSINESS_TYPE_CHOICES = (
    ('PAWNBROKER', 'Pawnbroker Only'),
    ('JEWELLER', 'Jeweller Only'),
    ('COMBINED', 'Pawnbroker & Jeweller'),
)
- business_type (CharField) - Primary business classification

# Enhanced License Types
LICENSE_TYPE_CHOICES = (
    ('PBL', 'Pawn Brokers License'),
    ('GST', 'Goods & Service Tax'),
    ('IMPORT_EXPORT', 'Import/Export License'),
    ('HALLMARK', 'Hallmark Certificate'),
    ('OTHER', 'Other'),
)
```

#### New Methods:
- `is_expired()` - Check if license is expired
- `days_until_expiry()` - Get days remaining
- `renew_license()` - Handle renewal logic
- `get_status_display_color()` - UI color coding
- `get_linked_licenses()` - Get related licenses (e.g., GST for a PBL)

### 2. New LicenseDocument Model

Store licenses and related documents:
```python
class LicenseDocument(models.Model):
    license = ForeignKey(License)
    document_type = CharField  # Certificate, Approval Letter, etc.
    document_file = FileField
    upload_date = DateTimeField(auto_now_add=True)
    expiry_date = DateField(optional)
```

### 3. Enhanced Forms

- Add workspace selection (filtered by user's workspace)
- Conditional fields based on license type
- Document upload field
- Better date pickers for expiry dates
- Status field with smart defaults

### 4. Enhanced Views

**LicenseListView Improvements:**
- Filter by workspace
- Filter by license type
- Filter by status
- Show expiry warnings
- Bulk operations (deactivate, mark expired)

**LicenseDetailView Improvements:**
- Show all linked licenses
- Display documents
- Show renewal history
- Calculate expiry info

**New Views:**
- `LicenseExpiryReportView` - Show licenses expiring soon
- `LicenseRenewalView` - Handle license renewal
- `UploadLicenseDocumentView` - Document management

### 5. Template Enhancements

**License List:**
- Group by license type
- Color-code by status
- Show expiry countdown
- Quick status indicators

**License Detail:**
- Tabbed interface (details, documents, linked licenses, history)
- Document preview/download
- Expiry warning banner
- Renewal action button

**License Form:**
- Progressive disclosure based on type
- Date range selectors
- Document upload widget
- Preview of selected documents

## Implementation Priority

1. **Phase 1 (High):** Workspace integration, status field, expiry tracking
2. **Phase 2 (High):** License types expansion, document model
3. **Phase 3 (Medium):** License documents upload, views enhancement
4. **Phase 4 (Medium):** Report views, renewal logic
5. **Phase 5 (Low):** Notifications, expiry alerts

## Database Impact

- Migration required to add new fields
- New model `LicenseDocument` requires new table
- Existing data migration script needed for status field population
- Index on `workspace` and `status` fields recommended

## UI/UX Improvements

- Color-coded license status badges
- Expiry countdown display
- Document carousel/gallery
- Linked license suggestions
- Bulk license type filtering
