# License Model Enhancement - Architecture & Data Flow

## 📐 Data Model Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Company (Workspace)                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ • name, logo, schema_name (multi-tenant)                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 1:N relationship
                           │
        ┌──────────────────▼────────────────┐
        │      License (Enhanced)           │
        ├──────────────────────────────────┤
        │ • name                           │
        │ • license_number (unique)        │
        │ • type (PBL, GST, etc.)         │
        │ • status (ACTIVE, EXPIRED, etc.)│
        │ • business_type (PAWNBROKER, etc)
        │ • shopname, propreitor          │
        │ • address, city, state, email   │
        │ • issuing_authority             │
        │ • date_issued, date_expires     │
        │ • is_renewable, is_active       │
        │ • workspace (FK to Company)     │
        └──────────────────────────────────┘
               │                   │
           1:N │                   │ 1:N
               │                   │
        ┌──────▼─────────┐  ┌──────▼──────────────┐
        │    Series      │  │ LicenseDocument     │
        ├────────────────┤  ├────────────────────┤
        │ • name         │  │ • document_type    │
        │ • prefix       │  │ • title            │
        │ • max_limit    │  │ • document_file    │
        │ • loan_type    │  │ • uploaded_by      │
        │ • is_active    │  │ • upload_date      │
        └────────────────┘  │ • expiry_date      │
               │            │ • is_verified      │
           1:N │            │ • is_active        │
               │            └────────────────────┘
        ┌──────▼─────────┐
        │  Loan (GivenLoan/TakenLoan)
        ├────────────────┤
        │ • loan_id      │
        │ • loan_amount  │
        │ • loan_date    │
        │ • status       │
        └────────────────┘
```

## 🔄 User Workflow

### Creating a License

```
User (in Workspace)
        │
        ▼
┌───────────────────┐
│ License List View │──── Filters: Type, Status, Business Type
│ (workspace filter)│
└─────────┬─────────┘
          │ Click: New License
          ▼
┌───────────────────┐
│ License Create    │
│ Form              │──── workspace auto-filled from user.profile
├───────────────────┤
│ • Basic Info      │
│ • Business Details│
│ • License Details │
│ • Dates & Renewal │
└─────────┬─────────┘
          │ Submit
          ▼
┌───────────────────┐
│ License Saved     │──── Auto-set status: ACTIVE (if not expired)
│ + Redirect        │──── Auto-index for searches
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ License Detail    │
│ View              │
├───────────────────┤
│ • Details Tab     │
│ • Documents Tab   │
│ • Linked Licenses │
│ • Series Tab      │
└───────────────────┘
```

### Managing License Documents

```
License Detail View
        │
        ├─► Upload Document Button
        │         │
        │         ▼
        │   Document Upload Form
        │         │
        │         ▼
        │   LicenseDocument Created
        │         │
        │         ▼
        │   Documents Tab Updated
        │
        └─► Documents Tab
                  │
                  ├─► Download Document (shows file size, type)
                  │
                  └─► Delete Document (with confirmation)
```

### License Expiry Management

```
License Created with date_expires
        │
        ▼
┌──────────────────────────────────┐
│ Automatic Status Check (viewed)  │
├──────────────────────────────────┤
│ is_expired() = False             │
│ is_expiring_soon(30) = False     │
│ Status = ACTIVE                  │
└──────────────┬───────────────────┘
               │
        [Days pass...]
               │
        ┌──────▼────────────┐
        │ 30 Days Before    │
        │ Expiry            │
        ├───────────────────┤
        │ is_expiring_soon()│
        │ = True            │
        │ Status = ACTIVE   │
        │ Warning shown     │
        └──────┬────────────┘
               │
        [More days pass...]
               │
        ┌──────▼─────────────┐
        │ Expiry Date        │
        │ Reached            │
        ├────────────────────┤
        │ is_expired()=True  │
        │ Status = EXPIRED   │
        │ Alert shown        │
        └──────┬─────────────┘
               │
               ▼
        ┌──────────────────┐
        │ Renewal Form     │──── Sets new date_expires
        │                  │──── Status = RENEWED
        │                  │──── Updates renewal_date
        └──────────────────┘
```

## 👁️ View Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    License Views                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ license_list                                     │  │
│ │ - Filters: type, status, business_type          │  │
│ │ - Workspace scoped                              │  │
│ │ - Auto-status updates on render                 │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ LicenseCreateView                                │  │
│ │ - Auto-assign workspace                         │  │
│ │ - Form with all fields                          │  │
│ │ - Redirect to detail on success                 │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ LicenseDetailView                                │  │
│ │ - Multi-tab interface                           │  │
│ │ - Status-based alerts                           │  │
│ │ - Document gallery                              │  │
│ │ - Linked licenses                               │  │
│ │ - Series management                             │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ LicenseUpdateView                                │  │
│ │ - Edit existing license                         │  │
│ │ - Preserve workspace                            │  │
│ │ - Form with all fields                          │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ LicenseDeleteView                                │  │
│ │ - Confirmation page                             │  │
│ │ - Cascade delete related                        │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ LicenseExpiryReportView                          │  │
│ │ - Licenses expiring in 90 days                  │  │
│ │ - Color-coded by urgency                        │  │
│ │ - Quick renewal action                          │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ LicenseDocumentUploadView                        │  │
│ │ - Upload documents                              │  │
│ │ - Set type, title, expiry                       │  │
│ │ - Track uploader                                │  │
│ │ - Redirect to license detail                    │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ LicenseDocumentDeleteView                        │  │
│ │ - Delete document with confirmation             │  │
│ │ - Redirect to license detail                    │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
│ ┌──────────────────────────────────────────────────┐  │
│ │ LicenseRenewalView                               │  │
│ │ - Specialized update for renewal                │  │
│ │ - Status → RENEWED                              │  │
│ │ - Update renewal_date                           │  │
│ │ - Warning alerts for expired                    │  │
│ └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 📋 Database Query Patterns

### Get All Licenses for Workspace with Status
```python
licenses = License.objects.filter(workspace=workspace,
                                   status='ACTIVE')
# Uses index: (workspace, status)
```

### Get Expiring Licenses
```python
from django.utils import timezone
from datetime import timedelta

licenses = License.objects.filter(
    workspace=workspace,
    date_expires__lte=timezone.now().date() + timedelta(days=30),
    date_expires__gte=timezone.now().date()
)
# Uses index: (date_expires)
```

### Get Licenses by Type
```python
licenses = License.objects.filter(workspace=workspace,
                                   type='GST')
# Uses index: (workspace, type)
```

### Get License with Documents and Series
```python
license = License.objects.select_related('workspace').prefetch_related(
    'documents',
    'series_set'
).get(pk=license_id)
```

## 🔐 Security Considerations

### Workspace Isolation
- ✅ All views filter by `request.user.profile.workspace`
- ✅ Create automatically assigns workspace
- ✅ No cross-workspace data access

### Document Upload
- ✅ File upload with type validation
- ✅ Upload directory uses timestamp for organization
- ✅ Upload user tracked for audit

### Deletion
- ✅ Cascade delete from License to Documents
- ✅ Series can only be deleted with confirmation

## 📊 Performance Optimizations

### Indexes
```sql
CREATE INDEX idx_workspace_status ON license(workspace_id, status);
CREATE INDEX idx_workspace_type ON license(workspace_id, type);
CREATE INDEX idx_status ON license(status);
CREATE INDEX idx_date_expires ON license(date_expires);
```

### Query Optimization
- Use `select_related('workspace')` for workspace info
- Use `prefetch_related('documents')` for document lists
- Use `prefetch_related('series_set')` for series lists
- Filter by workspace first (most restrictive)

### Admin Optimization
- Limit inline load: `extra = 1` in SeriesInline
- Only show active documents in list

## 🎯 URL Structure

```
/girvi/license/                          - List all (workspace-filtered)
/girvi/license/create/                   - Create form
/girvi/license/detail/<id>/              - Detail view
/girvi/license/update/<id>/              - Edit form
/girvi/license/<id>/delete/              - Delete form
/girvi/license/expiry-report/            - Expiry report
/girvi/license/<id>/document/upload/     - Upload document
/girvi/license/document/<id>/delete/     - Delete document (form)
/girvi/license/<id>/renew/               - Renew form
```

## 📱 Template Hierarchy

```
_base.html
├── license_list.html (extends _base.html)
├── license_form.html (extends _base.html)
│   └── Uses LicenseForm crispy template
├── license_detail.html (extends _base.html)
│   └── Multi-tab layout
├── license_confirm_delete.html (extends _base.html)
├── document_form.html (extends _base.html)
├── document_confirm_delete.html (extends _base.html)
├── license_renewal_form.html (extends _base.html)
└── license_expiry_report.html (extends _base.html)
```

## 🔄 Integration Points

### With Existing Systems
- ✅ Uses existing Company/Workspace model
- ✅ Uses existing CustomUser model
- ✅ Series unchanged (1:N relationship preserved)
- ✅ Loan models unchanged (access through Series)

### With Admin
- ✅ LicenseAdmin with fieldsets and filters
- ✅ LicenseDocumentAdmin full management
- ✅ Display methods for colors and status
- ✅ Inline document and series management

### With Forms
- ✅ Crispy forms integration
- ✅ Date widgets for all date fields
- ✅ Textarea for long text fields
- ✅ Select2 for FK relationships

---
**Updated**: February 24, 2026  
**Status**: ✅ Ready for Migration
