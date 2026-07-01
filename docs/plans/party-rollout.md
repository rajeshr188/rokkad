---
status: active
owner: project
updated: 2026-07-01
tags: [plans, party, contact, dea, migration]
related: [../domain/party.md, ../domain/contact.md, ../domain/accounting.md, ../adr/2026-06-18-party-domain-model.md, ../implementation/contact-model-migration.md, ../implementation/tenant-seeding.md]
---

# Party Rollout Plan

This plan tracks the phased introduction of the `party` app as the long-term external/internal business entity model.

The rollout is intentionally incremental. `contact.Customer` remains the compatibility model until operational apps are migrated.

## Current Status

Completed:

- Phase 0: ADR and domain documentation.
- Phase 1: Minimal tenant app and model layer.
- Phase 2: Canonical role seed data and tenant seed integration.
- Phase 3: `Customer.party` bridge and customer-to-party backfill.
- Phase 4: DEA party-aware account mapping and resolver with `Customer.account` compatibility.
- Phase 5: Girvi pilot integration for borrower/lender account resolution.
- Phase 6: Sales and Purchase integration.
- Phase 7: Party UI.
- Phase 7.1: Party profile data editing.
- Phase 7.2: Party contact validation and relationships.
- Phase 7.3: Party textual relation identity.
- Phase 7.4: Party profile photo camera capture.
- Phase 8: Customer conversion and duplicate merge.
- Party list filtered CSV/XLSX export for Owner/Admin users.

Next:

- Continue module-specific Party-first create/edit cutovers as those workflows are prioritized.

Pending:

- Approval Party migration is intentionally skipped for now because approval is not a current priority.

## Phase 0: Architecture Decision And Docs

Status: complete.

Files created or updated:

- `docs/adr/2026-06-18-party-domain-model.md`
- `docs/domain/party.md`
- `docs/domain/contact.md`
- `docs/domain/accounting.md`
- `docs/GLOSSARY.md`
- `docs/STATUS.md`

Acceptance:

- Party is accepted as the long-term external entity model.
- `Customer` remains a compatibility model during migration.
- Accounting account choice is documented as party + role + purpose, not party identity alone.

## Phase 1: Minimal Party App

Status: complete.

Files created or updated:

- `apps/tenant_apps/party/`
- `apps/tenant_apps/party/models/`
- `apps/tenant_apps/party/admin.py`
- `apps/tenant_apps/party/selectors.py`
- `apps/tenant_apps/party/facade.py`
- `apps/tenant_apps/party/tests/test_party_models.py`
- `apps/tenant_apps/party/migrations/0001_initial.py`
- `django_project/settings/base.py`

Models added:

- `Party`
- `PartyRoleType`
- `PartyRole`
- `PartyContactMethod`
- `PartyAddress`
- `PartyIdentifier`
- `PartyDocument`
- `PartyRelationship`

Validation:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test apps.tenant_apps.party.tests.test_party_models`
- `python manage.py migrate_schemas`

## Phase 2: Canonical Role Seeding

Status: complete.

Files created or updated:

- `apps/tenant_apps/party/services/role_seed.py`
- `apps/tenant_apps/party/management/commands/seed_party_roles.py`
- `apps/tenant_apps/party/tests/test_party_role_seed.py`
- `apps/orgs/management/commands/seed_tenant_defaults.py`
- `docs/implementation/tenant-seeding.md`

Seeded system roles:

- `CUSTOMER`
- `SUPPLIER`
- `BORROWER`
- `LENDER`
- `RETAILER`
- `WHOLESALER`
- `MANUFACTURER`
- `EMPLOYEE`
- `AGENT`
- `BROKER`
- `BANK`
- `TRANSPORTER`
- `INSURANCE_PROVIDER`
- `PORTAL_CUSTOMER`

Current tenant schemas seeded:

- `jsk`
- `lakshmipawnbroker`
- `jcl`
- `test3`

Validation:

- `python manage.py test apps.tenant_apps.party.tests.test_party_role_seed`
- `python manage.py seed_party_roles --schema <schema>`

## Phase 3: Customer Bridge And Backfill

Status: complete.

Files created or updated:

- `apps/tenant_apps/contact/models.py`
- `apps/tenant_apps/contact/admin.py`
- `apps/tenant_apps/contact/facade.py`
- `apps/tenant_apps/contact/migrations/0006_customer_party.py`
- `apps/tenant_apps/party/services/customer_bridge.py`
- `apps/tenant_apps/party/management/commands/backfill_parties_from_customers.py`
- `apps/tenant_apps/party/tests/test_customer_bridge.py`
- `docs/implementation/contact-model-migration.md`

Model change:

- Added nullable `Customer.party = OneToOneField("party.Party", on_delete=PROTECT, null=True, blank=True)`.

Mapping:

- Retail -> Party role `CUSTOMER`, segment `RETAIL`
- Wholesale -> Party role `CUSTOMER`, segment `WHOLESALE`
- Supplier -> Party role `SUPPLIER`

Backfilled tenant schemas:

- `jsk`: 426 customers, 0 missing, 426 parties.
- `lakshmipawnbroker`: 1067 customers, 0 missing, 1067 parties.
- `jcl`: 5431 customers, 0 missing, 5431 parties.
- `test3`: 1 customer, 0 missing, 1 party.

Validation:

- `python manage.py test apps.tenant_apps.party.tests.test_customer_bridge`
- `python manage.py migrate_schemas`
- `python manage.py backfill_parties_from_customers --schema <schema> --only-missing`

## Phase 4: DEA Party Account Mapping

Status: complete.

Goal:

Introduce party-aware account resolution while keeping the current `Customer.account` fallback.

Files to create:

- `apps/tenant_apps/dea/models/party_account.py`
- `apps/tenant_apps/dea/services/account_resolution.py`
- `apps/tenant_apps/dea/tests/test_party_account_resolution.py`

Files to modify:

- `apps/tenant_apps/dea/models/__init__.py`
- `apps/tenant_apps/dea/facades/accounts.py`
- `apps/tenant_apps/dea/facade.py`
- `apps/tenant_apps/dea/admin.py`
- `docs/domain/accounting.md`
- `docs/apps/dea/models.md`
- `docs/apps/dea/workflows.md`

Files created or updated:

- `apps/tenant_apps/dea/models/party_account.py`
- `apps/tenant_apps/dea/services/account_resolution.py`
- `apps/tenant_apps/dea/tests/test_party_account_resolution.py`
- `apps/tenant_apps/dea/migrations/0031_partyaccountmapping_and_more.py`
- `apps/tenant_apps/dea/models/account.py`
- `apps/tenant_apps/dea/models/__init__.py`
- `apps/tenant_apps/dea/facades/accounts.py`
- `apps/tenant_apps/dea/facade.py`
- `apps/tenant_apps/dea/admin.py`
- `apps/tenant_apps/contact/models.py`
- `docs/domain/accounting.md`
- `docs/apps/dea/models.md`
- `docs/apps/dea/workflows.md`

Model added:

- `PartyAccountMapping`
  - `party`
  - `role_key`
  - `purpose`
  - `account`
  - `control_ledger`
  - `is_default`
  - `status`
  - timestamps

Resolver API:

- `resolve_party_account(party, role_key, purpose, event_type=None, create=True)`
- `resolve_customer_account(customer, role_key=None, purpose=None, event_type=None)`
- `ensure_customer_account(customer)`

Compatibility change:

- `dea.Account.contact` is now a foreign key to `contact.Customer`, allowing more than one subledger account for the same bridged customer/party.
- `contact.Customer.account` remains as a read-only compatibility alias returning the first active DEA account for legacy callers.

Acceptance:

- Same party can have different accounts for customer receivable, supplier payable, borrower loan receivable, lender loan payable, customer advance, and supplier advance.
- Existing `ensure_customer_account()` remains compatible.
- Cross-app callers can use DEA facade account resolver functions.
- Existing posting rules are not forced to migrate in this phase.

Validation:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test apps.tenant_apps.dea.tests.test_party_account_resolution`
- `python manage.py migrate_schemas`

## Phase 5: Girvi Pilot Integration

Status: complete.

Goal:

Use the DEA resolver for Girvi borrower/lender accounting first.

Main targets:

- `apps/tenant_apps/girvi/service_modules/payment.py`
- `apps/tenant_apps/dea/posting/rules/party_accounts.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_payment.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_receipt.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_release.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_auction.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_sold.py`
- `apps/tenant_apps/dea/posting/rules/loan_repayment.py`
- `apps/tenant_apps/dea/posting/rules/takenloan_payment.py`
- `apps/tenant_apps/dea/posting/rules/takenloan_receipt.py`

Acceptance:

- `GivenLoan.borrower` resolves role `BORROWER`, purpose `BORROWER_LOAN_RECEIVABLE`.
- `TakenLoan.lender` resolves role `LENDER`, purpose `LENDER_LOAN_PAYABLE`.
- Existing Customer fallback remains available.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.dea.tests.test_party_account_resolution`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.girvi.tests.test_payment_integration_pr1_pr2.PR2DisbursalServiceTests`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.girvi.tests.test_interest_accrual_accounting.GivenLoanAccrualAwarePostingRuleTests`

Note:

- The full `apps.tenant_apps.girvi.tests.test_interest_accrual_accounting` module still has a stale test patch target for `JournalEntryVoucher` unrelated to the party account resolver change.

## Phase 6: Sales And Purchase Integration

Status: complete.

Goal:

Move sales and purchase account resolution away from `customer.account` and `supplier.account`.

Account purposes:

- Sales customer -> `CUSTOMER_RECEIVABLE`
- Purchase supplier -> `SUPPLIER_PAYABLE`
- Customer advance -> `CUSTOMER_ADVANCE`
- Supplier advance -> `SUPPLIER_ADVANCE`

Acceptance:

- Same party can appear as customer and supplier without reusing the same subledger account.
- Reports can preserve gross AR/AP and optionally show net exposure.

Files created or updated:

- `apps/tenant_apps/dea/posting/rules/party_accounts.py`
- `apps/tenant_apps/dea/posting/rules/sales_invoice.py`
- `apps/tenant_apps/dea/posting/rules/purchase_invoice.py`
- `apps/tenant_apps/dea/posting/resolver.py`
- `apps/tenant_apps/dea/tests/test_sales_purchase_party_posting.py`
- `docs/STATUS.md`
- `docs/AGENT_MEMORY.md`
- `docs/domain/accounting.md`
- `docs/apps/dea/workflows.md`

Implementation notes:

- Sales invoices resolve customer account role `CUSTOMER`, purpose `CUSTOMER_RECEIVABLE`.
- Purchase invoices resolve supplier/vendor account role `SUPPLIER`, purpose `SUPPLIER_PAYABLE`.
- Customer and supplier advance resolver helpers are available for future payment/advance posting rules.
- The DEA sales and purchase invoice posting rules now return the current `PostingBundle` shape.
- Ledger resolver aliases bridge stable posting keys to current seeded ledger names such as `Accounts Receivable`, `Sales`, `Output CGST`, and `Professional Services`.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.dea.tests.test_sales_purchase_party_posting`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.dea.tests.test_party_account_resolution`

## Phase 7: Party UI

Status: complete.

Goal:

Expose party list, detail, create/edit, role management, and account/ledger visibility.

Expected tabs:

- Overview
- Roles
- Contacts
- Addresses
- Accounts / Ledger
- Transactions
- Loans
- Sales
- Purchases
- Documents / KYC
- Notes / Activity

Files created or updated:

- `apps/tenant_apps/party/forms.py`
- `apps/tenant_apps/party/views.py`
- `apps/tenant_apps/party/urls.py`
- `apps/tenant_apps/party/tests/test_party_ui.py`
- `templates/party/list.html`
- `templates/party/detail.html`
- `templates/party/form.html`
- `templates/party/partials/linked_object_table.html`
- `django_project/tenant_urls.py`
- `templates/components/navigation/sidebar.html`
- `docs/STATUS.md`
- `docs/AGENT_MEMORY.md`
- `docs/domain/party.md`

Implementation notes:

- Tenant Party UI is available under `/party/`.
- The party list supports search, status filtering, role filtering, and create/edit access.
- Party detail shows Overview, Roles, Contacts, Addresses, Accounts / Ledger, Transactions, Loans, Sales, Purchases, Documents / KYC, and Notes / Activity tabs.
- Role management supports adding roles and ending active roles from the party detail page.
- Account visibility uses DEA `PartyAccountMapping` through the `dea_account_mappings` related name and links to DEA account and ledger detail pages.
- Linked sales, purchase, and loan activity is read through the `contact.Customer.party` compatibility bridge until Phase 9 migrates operational foreign keys.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_party_ui --keepdb`

## Phase 7.1: Party Profile Data Editing

Status: complete.

Goal:

Make the Party detail page the operational place for maintaining a party profile before duplicate merge and conversion work begins.

Files created or updated:

- `apps/tenant_apps/party/models/party.py`
- `apps/tenant_apps/party/models/contact.py`
- `apps/tenant_apps/party/forms.py`
- `apps/tenant_apps/party/views.py`
- `apps/tenant_apps/party/urls.py`
- `apps/tenant_apps/party/migrations/0002_party_profile_photo.py`
- `apps/tenant_apps/party/tests/test_party_ui.py`
- `templates/party/list.html`
- `templates/party/detail.html`
- `templates/party/form.html`
- `docs/STATUS.md`
- `docs/AGENT_MEMORY.md`
- `docs/domain/party.md`

Implementation notes:

- `Party.profile_photo` stores a single profile image under `party_profile_photos/` with UUID filenames.
- Party list and detail show profile photos with a fallback initial avatar.
- Party detail now supports inline add/edit/delete for contact methods, addresses, identifiers, and documents.
- Primary email and phone contacts sync to `Party.primary_email` and `Party.primary_phone`.
- Default address saves unset the previous default address for the same party/address type before saving.
- Identifier and document verification fields remain read-only in normal Party UI.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py makemigrations --check --dry-run`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_party_ui --keepdb`

## Phase 7.2: Party Contact Validation And Relationships

Status: complete.

Goal:

Tighten Party profile data quality and expose relationship management before duplicate merge and conversion work begins.

Files created or updated:

- `apps/tenant_apps/party/forms.py`
- `apps/tenant_apps/party/views.py`
- `apps/tenant_apps/party/urls.py`
- `apps/tenant_apps/party/selectors.py`
- `apps/tenant_apps/party/tests/test_party_ui.py`
- `templates/party/detail.html`
- `docs/STATUS.md`
- `docs/AGENT_MEMORY.md`
- `docs/domain/party.md`

Implementation notes:

- Phone, mobile, and WhatsApp contact values are validated with `django-phonenumber-field` using region `IN` and stored in E.164 format.
- Email contact values are validated and normalized to lowercase.
- Website contact values are URL-validated.
- Party detail now includes a Relationships tab for inline add/edit/delete of `PartyRelationship`.
- Outgoing relationships can be maintained from the current party, and incoming relationships are visible read-only.
- Relationship forms reject self-links and duplicate relationship tuples before database constraints are hit.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py makemigrations --check --dry-run`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_party_ui --keepdb`

## Phase 7.3: Party Textual Relation Identity

Status: complete.

Goal:

Capture local identity relation text such as `S/o`, `D/o`, `C/o`, and `W/o` even when the related person is not a saved Party.

Files created or updated:

- `apps/tenant_apps/party/models/party.py`
- `apps/tenant_apps/party/forms.py`
- `apps/tenant_apps/party/admin.py`
- `apps/tenant_apps/party/services/customer_bridge.py`
- `apps/tenant_apps/party/migrations/0003_party_relation_label_party_relation_name.py`
- `apps/tenant_apps/party/tests/test_party_ui.py`
- `apps/tenant_apps/party/tests/test_customer_bridge.py`
- `templates/party/list.html`
- `templates/party/detail.html`
- `templates/party/form.html`
- `docs/STATUS.md`
- `docs/AGENT_MEMORY.md`
- `docs/domain/party.md`

Implementation notes:

- `Party.relation_label` stores labels such as `S/o`, `D/o`, `C/o`, `W/o`, `H/o`, `F/o`, `P/o`, and `O/o`.
- `Party.relation_name` stores the related person name as text.
- Party forms require relation label and related person name to be entered together.
- Party list and detail display the textual relation separately from linked Party relationships.
- Customer bridge backfill maps legacy `Customer.relatedas` / `relatedto` into the new Party relation fields.
- Structured `PartyRelationship` remains reserved for relations where the other side is a saved Party.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py makemigrations --check --dry-run`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_party_ui apps.tenant_apps.party.tests.test_customer_bridge --keepdb`

## Phase 7.4: Party Profile Photo Camera Capture

Status: complete.

Goal:

Allow users to capture a party profile photo directly from the device camera while keeping the existing choose-file upload option.

Files created or updated:

- `apps/tenant_apps/party/views.py`
- `apps/tenant_apps/party/tests/test_party_ui.py`
- `templates/party/detail.html`
- `docs/STATUS.md`
- `docs/AGENT_MEMORY.md`
- `docs/domain/party.md`

Implementation notes:

- Party detail Overview now provides camera controls next to the profile photo file input.
- Browser-side capture uses `navigator.mediaDevices.getUserMedia`, draws the captured frame to a canvas, and submits it as `image_data`.
- The server decodes captured base64 image data into `Party.profile_photo` with a UUID filename.
- File upload remains supported from the same form.
- No database migration is required.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py makemigrations --check --dry-run`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_party_ui --keepdb`

## Phase 8: Customer Conversion And Duplicate Merge

Status: complete.

Goal:

Make duplicate party/customer cleanup safe and auditable.

Files created or updated:

- `apps/tenant_apps/party/services/party_merge.py`
- `apps/tenant_apps/party/forms.py`
- `apps/tenant_apps/party/views.py`
- `apps/tenant_apps/party/urls.py`
- `apps/tenant_apps/party/tests/test_party_merge.py`
- `apps/tenant_apps/party/tests/test_party_ui.py`
- `templates/party/list.html`
- `templates/party/detail.html`
- `templates/party/customer_convert.html`
- `docs/STATUS.md`
- `docs/AGENT_MEMORY.md`
- `docs/domain/party.md`
- `docs/plans/party-rollout.md`

Implementation notes:

- Party list now exposes a Convert Customer action for legacy customers that are not linked to a Party.
- Customer conversion reuses the existing `ensure_customer_party()` bridge service so roles, contacts, addresses, identifiers, and relation text are created consistently.
- Party detail now has a Merge tab where users can merge a duplicate Party into the current Party.
- Merge archives the duplicate source Party instead of deleting it.
- Merge moves non-conflicting roles, contact methods, addresses, identifiers, documents, Party relationships, and DEA party account mappings.
- Documents linked to duplicate-but-equivalent identifiers are repointed to the target identifier before being moved.
- Merge refuses to proceed when both parties are linked to legacy customers, when identifier values conflict for the same identifier type, or when active DEA account mappings overlap for the same role/purpose/event key.
- Duplicate active roles and relationships that would become invalid or duplicate are skipped and the archived source Party remains as the audit reference.
- No database migration is required.
- Party list exports filtered flat Party data to CSV/XLSX using `django-import-export`; detailed child records remain separate export candidates.

Acceptance:

- Staff can convert existing customers into parties.
- Duplicate merge preserves roles, contact data, documents, and audit history.
- Accounting mappings are not silently merged.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py makemigrations --check --dry-run`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_party_merge apps.tenant_apps.party.tests.test_party_ui --keepdb`

## Phase 9: Gradual Foreign-Key Migration

Status: complete for current prioritized scope. Approval is explicitly skipped.

Goal:

Move operational documents from Customer FK to Party FK using nullable shadow fields first.

Completed in first slice:

- `GivenLoan.borrower_party`
- `TakenLoan.lender_party`
- `sales.Invoice.party`
- `sales.Receipt.party`
- `purchase.Purchase.party`
- `purchase.Payment.party`
- `dea.SalesInvoiceVoucher.party`
- `dea.PurchaseInvoiceVoucher.party`
- Girvi given-loan create UI selects active Parties and auto-bridges the selected Party to compatibility `Customer` on save.

Files created or updated:

- `apps/tenant_apps/girvi/models/loan_refactored.py`
- `apps/tenant_apps/girvi/migrations/0022_givenloan_borrower_party_takenloan_lender_party_and_more.py`
- `apps/tenant_apps/sales/models/sale.py`
- `apps/tenant_apps/sales/models/receipt.py`
- `apps/tenant_apps/sales/migrations/0004_invoice_party_receipt_party_and_more.py`
- `apps/tenant_apps/purchase/models/purchase.py`
- `apps/tenant_apps/purchase/models/payment.py`
- `apps/tenant_apps/purchase/migrations/0002_payment_party_purchase_party_and_more.py`
- `apps/tenant_apps/dea/models/sales_invoice.py`
- `apps/tenant_apps/dea/models/purchase_invoice.py`
- `apps/tenant_apps/dea/migrations/0032_purchaseinvoicevoucher_party_and_more.py`
- `apps/tenant_apps/dea/posting/rules/party_accounts.py`
- `apps/tenant_apps/party/tests/test_operational_party_links.py`
- `docs/STATUS.md`
- `docs/AGENT_MEMORY.md`
- `docs/domain/party.md`
- `docs/plans/party-rollout.md`

Implementation notes:

- Shadow Party fields are nullable and do not replace existing Customer/vendor/borrower/lender fields.
- New saves auto-fill the shadow Party field when the legacy Customer is already bridged to Party.
- New Girvi given-loan creation is Party-first: `LoanCreateForm` selects `borrower_party`, `ensure_party_customer()` creates/reuses the compatibility `Customer`, and `LoanCreationService` writes both `borrower` and `borrower_party`.
- Tenant migrations backfill existing rows from `Customer.party` where that bridge exists.
- DEA posting account resolution now prefers explicit Party shadow fields and falls back to legacy Customer resolution.
- Direct Party-only account resolution works when the Party already has a matching DEA `PartyAccountMapping`; automatic account creation still requires the legacy Customer bridge for now.

Candidate fields:

- `Approval.party` is skipped until approval workflows become a priority again.

Acceptance:

- Historical documents remain readable.
- New documents can resolve party directly.
- Old Customer fields are kept until compatibility is no longer required.
- Notification recipient surfaces can resolve Party directly while keeping Customer compatibility.

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py makemigrations --check --dry-run`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_operational_party_links --keepdb`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.dea.tests.test_party_account_resolution apps.tenant_apps.dea.tests.test_sales_purchase_party_posting --keepdb`

Completed final slice:

- `notify.Notification.party`
- `notify_v2.NotificationRecipient.party`
- Save-time sync from `customer.party` for both notification surfaces.
- Tenant migration backfills for existing bridged notification rows.

Files created or updated in final slice:

- `apps/tenant_apps/notify/models.py`
- `apps/tenant_apps/notify/forms.py`
- `apps/tenant_apps/notify/views.py`
- `apps/tenant_apps/notify/migrations/0005_notification_party.py`
- `apps/tenant_apps/notify_v2/models.py`
- `apps/tenant_apps/notify_v2/services/batch_service.py`
- `apps/tenant_apps/notify_v2/migrations/0002_notificationrecipient_party.py`
- `apps/tenant_apps/party/tests/test_operational_party_links.py`

## Phase 10: Portal Support

Status: complete for read-only MVP.

Goal:

Support external party-linked portal users without making them workspace members.

Proposed model:

- `PartyPortalAccess`
  - `party`
  - `user`
  - `status`
  - `invited_at`
  - `activated_at`
  - `revoked_at`

Acceptance:

- Party can be linked to a user identity.
- Portal users can only see documents for their linked party.

Implementation notes:

- `PartyPortalAccess` is a tenant model linking a user to a Party without creating a workspace membership.
- Only `ACTIVE` access grants resolve through `resolve_portal_identity()`.
- Tenant `/portal/...` routes are live for dashboard, loans, invoices, payments, documents, and statements.
- Public URLConf still does not expose `/portal/...`.
- Portal selectors validate `PortalIdentity` first and filter by the resolved Party.
- The portal is read-only; no customer-facing mutations are exposed.
- Selector/render hardening now covers real tenant Girvi loan, sales invoice,
  and payment fixtures for the granted Party while proving another Party's
  loan/invoice/payment data does not appear in selectors or rendered portal
  pages.
- Portal invoice/payment rows render amount and currency explicitly instead of
  relying on implicit `Money.__str__` formatting.

Files created or updated:

- `apps/tenant_apps/party/models/portal.py`
- `apps/tenant_apps/party/models/__init__.py`
- `apps/tenant_apps/party/admin.py`
- `apps/tenant_apps/party/portal_access.py`
- `apps/tenant_apps/party/portal_selectors.py`
- `apps/tenant_apps/party/portal_views.py`
- `apps/tenant_apps/party/portal_urls.py`
- `apps/tenant_apps/party/migrations/0005_partyportalaccess.py`
- `apps/tenant_apps/party/tests/test_party_portal.py`
- `django_project/tenant_urls.py`
- `templates/base_customer_portal.html`
- `templates/components/navigation/customer_portal_nav.html`
- `templates/party/portal/dashboard.html`
- `templates/party/portal/loans.html`
- `templates/party/portal/invoices.html`
- `templates/party/portal/payments.html`
- `templates/party/portal/documents.html`
- `templates/party/portal/statements.html`
- `static/css/customer_portal.css`

Validation:

- `.\\.venv314\\Scripts\\python.exe manage.py check`
- `.\\.venv314\\Scripts\\python.exe manage.py makemigrations --check --dry-run`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_operational_party_links apps.tenant_apps.party.tests.test_party_portal --keepdb`
- `.\\.venv314\\Scripts\\python.exe manage.py test apps.tenant_apps.party.tests.test_party_portal --keepdb`
