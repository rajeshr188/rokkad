---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# License Model Enhancement - Architecture & Data Flow

## ðŸ“ Data Model Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                        Company (Workspace)                       â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚  â”‚ â€¢ name, logo, schema_name (multi-tenant)                  â”‚ â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚ 1:N relationship
                           â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚      License (Enhanced)           â”‚
        â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
        â”‚ â€¢ name                           â”‚
        â”‚ â€¢ license_number (unique)        â”‚
        â”‚ â€¢ type (PBL, GST, etc.)         â”‚
        â”‚ â€¢ status (ACTIVE, EXPIRED, etc.)â”‚
        â”‚ â€¢ business_type (PAWNBROKER, etc)
        â”‚ â€¢ shopname, propreitor          â”‚
        â”‚ â€¢ address, city, state, email   â”‚
        â”‚ â€¢ issuing_authority             â”‚
        â”‚ â€¢ date_issued, date_expires     â”‚
        â”‚ â€¢ is_renewable, is_active       â”‚
        â”‚ â€¢ workspace (FK to Company)     â”‚
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚                   â”‚
           1:N â”‚                   â”‚ 1:N
               â”‚                   â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚    Series      â”‚  â”‚ LicenseDocument     â”‚
        â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤  â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
        â”‚ â€¢ name         â”‚  â”‚ â€¢ document_type    â”‚
        â”‚ â€¢ prefix       â”‚  â”‚ â€¢ title            â”‚
        â”‚ â€¢ max_limit    â”‚  â”‚ â€¢ document_file    â”‚
        â”‚ â€¢ loan_type    â”‚  â”‚ â€¢ uploaded_by      â”‚
        â”‚ â€¢ is_active    â”‚  â”‚ â€¢ upload_date      â”‚
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚ â€¢ expiry_date      â”‚
               â”‚            â”‚ â€¢ is_verified      â”‚
           1:N â”‚            â”‚ â€¢ is_active        â”‚
               â”‚            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
        â”Œâ”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚  Loan (GivenLoan/TakenLoan)
        â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
        â”‚ â€¢ loan_id      â”‚
        â”‚ â€¢ loan_amount  â”‚
        â”‚ â€¢ loan_date    â”‚
        â”‚ â€¢ status       â”‚
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## ðŸ”„ User Workflow

### Creating a License

```
User (in Workspace)
        â”‚
        â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ License List View â”‚â”€â”€â”€â”€ Filters: Type, Status, Business Type
â”‚ (workspace filter)â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
          â”‚ Click: New License
          â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ License Create    â”‚
â”‚ Form              â”‚â”€â”€â”€â”€ workspace auto-filled from user.profile
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ â€¢ Basic Info      â”‚
â”‚ â€¢ Business Detailsâ”‚
â”‚ â€¢ License Details â”‚
â”‚ â€¢ Dates & Renewal â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
          â”‚ Submit
          â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ License Saved     â”‚â”€â”€â”€â”€ Auto-set status: ACTIVE (if not expired)
â”‚ + Redirect        â”‚â”€â”€â”€â”€ Auto-index for searches
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
          â”‚
          â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ License Detail    â”‚
â”‚ View              â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ â€¢ Details Tab     â”‚
â”‚ â€¢ Documents Tab   â”‚
â”‚ â€¢ Linked Licenses â”‚
â”‚ â€¢ Series Tab      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Managing License Documents

```
License Detail View
        â”‚
        â”œâ”€â–º Upload Document Button
        â”‚         â”‚
        â”‚         â–¼
        â”‚   Document Upload Form
        â”‚         â”‚
        â”‚         â–¼
        â”‚   LicenseDocument Created
        â”‚         â”‚
        â”‚         â–¼
        â”‚   Documents Tab Updated
        â”‚
        â””â”€â–º Documents Tab
                  â”‚
                  â”œâ”€â–º Download Document (shows file size, type)
                  â”‚
                  â””â”€â–º Delete Document (with confirmation)
```

### License Expiry Management

```
License Created with date_expires
        â”‚
        â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Automatic Status Check (viewed)  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ is_expired() = False             â”‚
â”‚ is_expiring_soon(30) = False     â”‚
â”‚ Status = ACTIVE                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚
        [Days pass...]
               â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚ 30 Days Before    â”‚
        â”‚ Expiry            â”‚
        â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
        â”‚ is_expiring_soon()â”‚
        â”‚ = True            â”‚
        â”‚ Status = ACTIVE   â”‚
        â”‚ Warning shown     â”‚
        â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚
        [More days pass...]
               â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚ Expiry Date        â”‚
        â”‚ Reached            â”‚
        â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
        â”‚ is_expired()=True  â”‚
        â”‚ Status = EXPIRED   â”‚
        â”‚ Alert shown        â”‚
        â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚
               â–¼
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚ Renewal Form     â”‚â”€â”€â”€â”€ Sets new date_expires
        â”‚                  â”‚â”€â”€â”€â”€ Status = RENEWED
        â”‚                  â”‚â”€â”€â”€â”€ Updates renewal_date
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## ðŸ‘ï¸ View Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    License Views                        â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ license_list                                     â”‚  â”‚
â”‚ â”‚ - Filters: type, status, business_type          â”‚  â”‚
â”‚ â”‚ - Workspace scoped                              â”‚  â”‚
â”‚ â”‚ - Auto-status updates on render                 â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ LicenseCreateView                                â”‚  â”‚
â”‚ â”‚ - Auto-assign workspace                         â”‚  â”‚
â”‚ â”‚ - Form with all fields                          â”‚  â”‚
â”‚ â”‚ - Redirect to detail on success                 â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ LicenseDetailView                                â”‚  â”‚
â”‚ â”‚ - Multi-tab interface                           â”‚  â”‚
â”‚ â”‚ - Status-based alerts                           â”‚  â”‚
â”‚ â”‚ - Document gallery                              â”‚  â”‚
â”‚ â”‚ - Linked licenses                               â”‚  â”‚
â”‚ â”‚ - Series management                             â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ LicenseUpdateView                                â”‚  â”‚
â”‚ â”‚ - Edit existing license                         â”‚  â”‚
â”‚ â”‚ - Preserve workspace                            â”‚  â”‚
â”‚ â”‚ - Form with all fields                          â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ LicenseDeleteView                                â”‚  â”‚
â”‚ â”‚ - Confirmation page                             â”‚  â”‚
â”‚ â”‚ - Cascade delete related                        â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ LicenseExpiryReportView                          â”‚  â”‚
â”‚ â”‚ - Licenses expiring in 90 days                  â”‚  â”‚
â”‚ â”‚ - Color-coded by urgency                        â”‚  â”‚
â”‚ â”‚ - Quick renewal action                          â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ LicenseDocumentUploadView                        â”‚  â”‚
â”‚ â”‚ - Upload documents                              â”‚  â”‚
â”‚ â”‚ - Set type, title, expiry                       â”‚  â”‚
â”‚ â”‚ - Track uploader                                â”‚  â”‚
â”‚ â”‚ - Redirect to license detail                    â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ LicenseDocumentDeleteView                        â”‚  â”‚
â”‚ â”‚ - Delete document with confirmation             â”‚  â”‚
â”‚ â”‚ - Redirect to license detail                    â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚ â”‚ LicenseRenewalView                               â”‚  â”‚
â”‚ â”‚ - Specialized update for renewal                â”‚  â”‚
â”‚ â”‚ - Status â†’ RENEWED                              â”‚  â”‚
â”‚ â”‚ - Update renewal_date                           â”‚  â”‚
â”‚ â”‚ - Warning alerts for expired                    â”‚  â”‚
â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                                                         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## ðŸ“‹ Database Query Patterns

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

## ðŸ” Security Considerations

### Workspace Isolation
- âœ… All views filter by `request.user.profile.workspace`
- âœ… Create automatically assigns workspace
- âœ… No cross-workspace data access

### Document Upload
- âœ… File upload with type validation
- âœ… Upload directory uses timestamp for organization
- âœ… Upload user tracked for audit

### Deletion
- âœ… Cascade delete from License to Documents
- âœ… Series can only be deleted with confirmation

## ðŸ“Š Performance Optimizations

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

## ðŸŽ¯ URL Structure

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

## ðŸ“± Template Hierarchy

```
_base.html
â”œâ”€â”€ license_list.html (extends _base.html)
â”œâ”€â”€ license_form.html (extends _base.html)
â”‚   â””â”€â”€ Uses LicenseForm crispy template
â”œâ”€â”€ license_detail.html (extends _base.html)
â”‚   â””â”€â”€ Multi-tab layout
â”œâ”€â”€ license_confirm_delete.html (extends _base.html)
â”œâ”€â”€ document_form.html (extends _base.html)
â”œâ”€â”€ document_confirm_delete.html (extends _base.html)
â”œâ”€â”€ license_renewal_form.html (extends _base.html)
â””â”€â”€ license_expiry_report.html (extends _base.html)
```

## ðŸ”„ Integration Points

### With Existing Systems
- âœ… Uses existing Company/Workspace model
- âœ… Uses existing CustomUser model
- âœ… Series unchanged (1:N relationship preserved)
- âœ… Loan models unchanged (access through Series)

### With Admin
- âœ… LicenseAdmin with fieldsets and filters
- âœ… LicenseDocumentAdmin full management
- âœ… Display methods for colors and status
- âœ… Inline document and series management

### With Forms
- âœ… Crispy forms integration
- âœ… Date widgets for all date fields
- âœ… Textarea for long text fields
- âœ… Select2 for FK relationships

---
**Updated**: February 24, 2026  
**Status**: âœ… Ready for Migration

