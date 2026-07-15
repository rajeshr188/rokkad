---
status: active
owner: project
updated: 2026-07-09
tags: [domain, party, schema, models]
related: [party.md, ../plans/party-rollout.md, ../adr/2026-06-18-party-domain-model.md]
---

# Party App Model Schema

This document describes the copyable model schema for the `party` app.

The Party app is the shared identity layer for people and organizations. A `Party` is the real-world entity. `PartyRole` records why that entity participates in a business workflow, such as customer, supplier, borrower, lender, employee, broker, bank, or portal customer.

## Core Design

```text
Party = identity
PartyRole = business capacity
PartyContactMethod = communication point
PartyAddress = location
PartyIdentifier = KYC/tax/government identifier
PartyDocument = uploaded proof or supporting document
PartyRelationship = link between two saved parties
PartyPortalAccess = explicit external portal grant
```

Do not create separate master identities for customer, supplier, borrower, or lender when the same real-world entity can play multiple roles.

## Relationship Map

```text
Party
  ├── PartyRole
  │     └── PartyRoleType
  ├── PartyContactMethod
  ├── PartyAddress
  ├── PartyIdentifier
  │     └── PartyDocument
  ├── PartyDocument
  ├── PartyRelationship as from_party
  ├── PartyRelationship as to_party
  └── PartyPortalAccess
        └── User
```

## PartyCodeSequence

Used to generate tenant-local party codes such as `P-000001`.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `key` | CharField(32) | yes | Unique sequence key, normally `PARTY` |
| `next_number` | PositiveIntegerField | yes | Next number to allocate |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |

Constraints:

| Constraint | Purpose |
|---|---|
| Unique `key` | One row per sequence key |

Behavior:

- Code generation locks the sequence row before incrementing.
- The current implementation generates `P-000001`, `P-000002`, and so on.
- Existing codes are checked before returning a candidate, so stale sequence values are skipped.

## Party

Main identity table for a person, organization, bank, government body, or internal workspace entity.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `party_code` | CharField(32) | yes | Unique, indexed, auto-generated when blank |
| `party_type` | CharField(32) | yes | Legal or natural entity form |
| `display_name` | CharField(255) | yes | Primary visible name |
| `legal_name` | CharField(255) | no | Legal or registered name |
| `normalized_name` | CharField(255) | no | Search-friendly normalized name |
| `relation_label` | CharField(16) | no | Text relation label such as `S/o` or `C/o` |
| `relation_name` | CharField(255) | no | Related person's name as plain text |
| `primary_phone` | CharField(32) | no | Denormalized primary phone |
| `primary_email` | EmailField | no | Denormalized primary email |
| `profile_photo` | ImageField | no | Uploaded profile photo |
| `tax_pan` | CharField(16) | no | Indexed PAN |
| `gstin` | CharField(24) | no | Indexed GSTIN |
| `risk_level` | CharField(32) | no | Optional operational risk label |
| `credit_hold` | BooleanField | yes | Indexed credit block flag |
| `status` | CharField(16) | yes | Party lifecycle state |
| `metadata` | JSONField | yes | Flexible extra data |
| `created_at` | DateTimeField | yes | Auto-created timestamp |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |
| `created_by` | FK User | no | User that created the party |
| `updated_by` | FK User | no | User that last updated the party |

`party_type` choices:

```text
INDIVIDUAL
ORGANIZATION
BANK
GOVERNMENT
INTERNAL_WORKSPACE
OTHER
```

`status` choices:

```text
ACTIVE
INACTIVE
BLOCKED
ARCHIVED
```

`relation_label` choices:

```text
SON_OF
DAUGHTER_OF
CARE_OF
PARENT_OF
FATHER_OF
WIFE_OF
HUSBAND_OF
OTHER
```

Indexes:

| Index | Purpose |
|---|---|
| `party_code` | Fast direct lookup by code |
| `display_name` | Search/list ordering |
| `party_type` | Type filtering |
| `normalized_name` | Search and duplicate review |
| `tax_pan` | KYC/tax duplicate review |
| `gstin` | GST duplicate review |
| `status`, `party_type` | Common list filtering |
| `credit_hold` | Credit block filtering |

Behavior:

- If `party_code` is blank, the system generates a sequential code.
- If `normalized_name` is blank, it is derived from `display_name`.
- `relation_label` and `relation_name` are for text identity like `S/o Kumar`, where Kumar may not be a saved Party.
- Use `PartyRelationship` when both sides are saved Party records.

## PartyRoleType

Seeded lookup table for available business roles.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `key` | CharField(64) | yes | Unique, indexed, canonical role key |
| `label` | CharField(128) | yes | Human-readable role label |
| `description` | TextField | no | Optional role description |
| `is_system` | BooleanField | yes | Whether this is a system-seeded role |
| `is_active` | BooleanField | yes | Whether this role can be assigned |
| `sort_order` | PositiveIntegerField | yes | Display order |

Common seeded keys:

```text
CUSTOMER
SUPPLIER
BORROWER
LENDER
RETAILER
WHOLESALER
MANUFACTURER
EMPLOYEE
AGENT
BROKER
BANK
TRANSPORTER
INSURANCE_PROVIDER
PORTAL_CUSTOMER
```

Behavior:

- `key` is stripped and uppercased on save.
- Workflow and posting code should use stable role keys, not display labels.

## PartyRole

Assigns a role to a Party.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `party` | FK Party | yes | Owning party; cascades on party delete |
| `role_type` | FK PartyRoleType | yes | Protected role type |
| `status` | CharField(16) | yes | Role lifecycle state |
| `segment` | CharField(64) | no | Optional role segment such as `RETAIL` or `WHOLESALE` |
| `effective_from` | DateField | no | Optional start date |
| `effective_to` | DateField | no | Optional end date |
| `metadata` | JSONField | yes | Flexible role-specific data |
| `created_at` | DateTimeField | yes | Auto-created timestamp |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |

`status` choices:

```text
ACTIVE
INACTIVE
ENDED
```

Constraints:

| Constraint | Purpose |
|---|---|
| One active role per `party` + `role_type` | Prevent duplicate active role assignments |

Indexes:

| Index | Purpose |
|---|---|
| `party`, `status` | Active role lookup for a party |
| `role_type`, `status` | Party list filtering by active role |

Example:

```text
Party: Raj Kumar
Roles:
  CUSTOMER, segment RETAIL
  BORROWER
```

## PartyContactMethod

Stores many contact methods for one Party.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `party` | FK Party | yes | Owning party; cascades on party delete |
| `contact_type` | CharField(16) | yes | Contact method type |
| `label` | CharField(64) | no | Optional label such as `Office` or `Home` |
| `value` | CharField(255) | yes | Raw contact value |
| `normalized_value` | CharField(255) | no | Indexed normalized value |
| `is_primary` | BooleanField | yes | Primary flag within contact type |
| `is_verified` | BooleanField | yes | Verification flag |
| `created_at` | DateTimeField | yes | Auto-created timestamp |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |

`contact_type` choices:

```text
PHONE
MOBILE
WHATSAPP
EMAIL
WEBSITE
OTHER
```

Constraints:

| Constraint | Purpose |
|---|---|
| One primary contact per `party` + `contact_type` | Allows one primary phone, one primary email, etc. |

Indexes:

| Index | Purpose |
|---|---|
| `party`, `contact_type` | Contact tab/list lookup |
| `normalized_value` | Search and duplicate review |

Behavior:

- `normalized_value` is currently stored as lowercase trimmed `value`.
- Application forms validate phone/mobile/WhatsApp and email/website formats.
- `Party.primary_phone` and `Party.primary_email` are denormalized summary fields.

## PartyAddress

Stores multiple addresses per Party.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `party` | FK Party | yes | Owning party; cascades on party delete |
| `address_type` | CharField(16) | yes | Address purpose |
| `line1` | CharField(255) | yes | Address line 1 |
| `line2` | CharField(255) | no | Address line 2 |
| `area` | CharField(128) | no | Area/locality |
| `city` | CharField(128) | yes | City |
| `state` | CharField(128) | no | State |
| `postal_code` | CharField(24) | no | Postal or ZIP code |
| `country` | CharField(2) | yes | ISO-like country code, default `IN` |
| `is_default` | BooleanField | yes | Default flag within address type |
| `is_verified` | BooleanField | yes | Verification flag |
| `created_at` | DateTimeField | yes | Auto-created timestamp |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |

`address_type` choices:

```text
REGISTERED
BILLING
SHIPPING
HOME
WORK
KYC
OTHER
```

Constraints:

| Constraint | Purpose |
|---|---|
| One default address per `party` + `address_type` | Allows one default billing address, one default KYC address, etc. |

Indexes:

| Index | Purpose |
|---|---|
| `party`, `address_type` | Address tab/list lookup |
| `city`, `state` | Location filtering |

## PartyIdentifier

Stores KYC, tax, and government identifiers.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `party` | FK Party | yes | Owning party; cascades on party delete |
| `identifier_type` | CharField(32) | yes | Identifier kind |
| `value` | CharField(128) | yes | Raw identifier value |
| `masked_value` | CharField(128) | no | Safe display value |
| `value_hash` | CharField(128) | no | Indexed hash for duplicate detection |
| `is_verified` | BooleanField | yes | Verification flag |
| `verified_at` | DateTimeField | no | Verification timestamp |
| `expires_on` | DateField | no | Expiry date |
| `metadata` | JSONField | yes | Flexible extra data |
| `created_at` | DateTimeField | yes | Auto-created timestamp |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |

`identifier_type` choices:

```text
PAN
AADHAAR
GSTIN
CIN
UDYAM
PASSPORT
DRIVING_LICENSE
OTHER
```

Constraints:

| Constraint | Purpose |
|---|---|
| One identifier per `party` + `identifier_type` | Prevent duplicate PAN/Aadhaar/GSTIN rows on the same party |

Indexes:

| Index | Purpose |
|---|---|
| `identifier_type`, `value_hash` | Duplicate and KYC review |
| `party`, `identifier_type` | Party KYC lookup |

Guidance:

- Use `masked_value` for UI display of sensitive identifiers.
- Use `value_hash` for duplicate detection where raw values should not be exposed.

## PartyDocument

Stores uploaded documents for a Party.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `party` | FK Party | yes | Owning party; cascades on party delete |
| `document_type` | CharField(32) | yes | Document kind |
| `title` | CharField(255) | yes | Human-readable document title |
| `file` | FileField | no | Uploaded document file |
| `identifier` | FK PartyIdentifier | no | Optional identifier this document supports |
| `is_verified` | BooleanField | yes | Verification flag |
| `verified_at` | DateTimeField | no | Verification timestamp |
| `expires_on` | DateField | no | Expiry date |
| `metadata` | JSONField | yes | Flexible extra data |
| `created_at` | DateTimeField | yes | Auto-created timestamp |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |

`document_type` choices:

```text
KYC
TAX
CONTRACT
LICENSE
OTHER
```

Indexes:

| Index | Purpose |
|---|---|
| `party`, `document_type` | Document tab/list lookup |
| `expires_on` | Expiry review |

Upload path:

```text
party_documents/<party_id>/<filename>
```

## PartyRelationship

Links one saved Party to another saved Party.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `from_party` | FK Party | yes | Source party |
| `to_party` | FK Party | yes | Target party |
| `relationship_type` | CharField(32) | yes | Relationship kind |
| `notes` | TextField | no | Optional notes |
| `is_active` | BooleanField | yes | Active flag |
| `created_at` | DateTimeField | yes | Auto-created timestamp |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |

`relationship_type` choices:

```text
CONTACT_PERSON
EMPLOYER
EMPLOYEE
BROKER
AGENT
RELATED_BUSINESS
FAMILY
OTHER
```

Constraints:

| Constraint | Purpose |
|---|---|
| Unique `from_party` + `to_party` + `relationship_type` | Prevent duplicate relationship rows |
| `from_party` cannot equal `to_party` | Prevent self-relationships |

Indexes:

| Index | Purpose |
|---|---|
| `from_party`, `relationship_type` | Outgoing relationship lookup |
| `to_party`, `relationship_type` | Incoming relationship lookup |

Use this only when both related entities are saved as Party records.

## PartyPortalAccess

Explicit grant linking an authenticated user to a Party for external portal access.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | AutoField | yes | Primary key |
| `party` | FK Party | yes | Protected party reference |
| `user` | FK User | yes | Auth user; cascades on user delete |
| `status` | CharField(16) | yes | Portal grant lifecycle state |
| `invited_at` | DateTimeField | yes | Defaults to current time |
| `activated_at` | DateTimeField | no | Activation timestamp |
| `revoked_at` | DateTimeField | no | Revocation timestamp |
| `created_at` | DateTimeField | yes | Auto-created timestamp |
| `updated_at` | DateTimeField | yes | Auto-updated timestamp |

`status` choices:

```text
INVITED
ACTIVE
SUSPENDED
REVOKED
```

Constraints:

| Constraint | Purpose |
|---|---|
| One live grant per `party` + `user` where status is `INVITED`, `ACTIVE`, or `SUSPENDED` | Prevent duplicate active portal relationships |

Indexes:

| Index | Purpose |
|---|---|
| `user`, `status` | Resolve portal identity for authenticated user |
| `party`, `status` | List portal grants for a Party |

Behavior:

- `activate()` sets status to `ACTIVE` and fills `activated_at` when missing.
- `revoke()` sets status to `REVOKED` and fills `revoked_at`.
- Portal access must be explicit. Do not infer it from matching email or phone.

## Copying Notes

When copying this schema to another project:

- Keep `Party` as the identity table.
- Keep `PartyRoleType` as seeded data with stable keys.
- Use `PartyRole` for customer/supplier/borrower/lender behavior.
- Keep contact methods, addresses, identifiers, and documents as child tables.
- Use text relation fields on `Party` for local identity text such as `S/o Kumar`.
- Use `PartyRelationship` only when the related entity exists as another Party.
- Use `PartyPortalAccess` only for explicit external-user access.
- Do not put accounting account fields directly on `Party`; accounting should resolve accounts by party, role, purpose, and business event in the accounting module.
