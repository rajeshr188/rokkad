---
status: accepted
owner: project
updated: 2026-09-09
tags: [saas, tenancy, rls, licenses, authorization, onboarding]
related:
  - ../architecture/control-plane-contracts.md
  - 2026-08-17-workspace-authorization-contract.md
  - ../plans/saas-access-media-and-onboarding.md
---

# Organization tenancy with license-scoped loan access

## Decision and implementation status

The organization/workspace remains the SaaS tenant, with licenses inside it.
The owner clarified that license scoping must be **optional and owner-configurable**.
Organization-wide access remains the current behavior, subject to action permissions.
No license-scoping implementation is authorized now: it must come last, after a
fresh design review and the owner's explicit approval.

The earlier "all loans under assigned licenses" statement was an interpretation for
a possible scoped mode, not a universal rule. Exact scope modes and assignment
semantics must be reconsidered in that final review. Do not infer personal/creator
ownership restrictions either. Borrower profiles remain shared within the organization
subject to viewing permission. Action-permission fixes, media privacy and onboarding
improvements proceed independently of this deferred scope feature.

## Responsibilities

| Concept | Responsibility |
| --- | --- |
| User | Person signing in; may belong to several organizations |
| Organization/workspace (`Company`) | Business-data owner, membership, subscription and settings boundary |
| Membership | Whether a person belongs to that organization |
| Role/actions | What operations that member may perform |
| License assignment (future) | Which lending records that member may access within the organization |
| License | Lending authority and its business metadata/validity |
| Series | Numbering under a license; not a separate tenant |
| Loan | Belongs to a workspace and license; drives scope for its related evidence |

An organization need not represent an incorporated company: a sole proprietor's
business has the same ownership and subscription boundary. One owner can own or
join multiple independent organizations without sharing their data automatically.

## Current access and deferred scope design

- Current staff access is organization-wide, subject to each action's permission.
  There are no license-assignment filters today; do not introduce them in another slice.
- Borrower profiles are shared within the organization subject to borrower-view
  permission. Viewing does not imply profile editing or bulk export authority.
- Optional license restrictions must be configurable by the owner, and must be
  reviewed and explicitly approved before implementation. Existing access must not
  silently become restricted. The final choice of modes/defaults is still open.
- If a restricted mode is later approved, scope must cover related collateral,
  releases, documents, aggregates, reports, searches and notifications, including
  indirect data exposed on shared borrower profiles. IDs and direct URLs cannot bypass it.
- Organization membership remains mandatory. Removing membership removes future
  organization access; any later assignment revocation needs equivalent coverage.
- The owner retains organization authority. Roles/actions and optional record scope
  remain separate concepts. No assumption is made that staff can only access loans
  they created, or that assigned-license access must always be enabled.
- A license is not assumed to be a branch. Neither license nor branch scope may be
  implemented before the deferred review and approval.

## Why retain the organization

One business may operate multiple licenses while sharing a borrower directory,
team, subscription, rates, settings and owner reports. Making each license a tenant
would require duplication or cross-tenant sharing for those ordinary operations,
and likely recreate an organization above licenses. License expiry or replacement
must not redefine ownership of retained loans and evidence.

A separately owned/operated business with independent billing, staff and records
should use a separate organization, even if it has only one license. Shared tables
with workspace predicates remain a reasonable pooled-SaaS architecture; this is not
a claim of unlimited performance or a completed security audit. Capacity contention,
indexes, query plans, and customer-specific restore/export operations still matter.

## Isolation, authorization and lifecycle are separate

Explicit workspace identity -> membership/lifecycle validation -> request workspace
-> transaction-local PostgreSQL context -> workspace RLS -> action authorization
-> future license/object scope -> loan lifecycle validation.

The diagram describes responsibilities, not a requirement to perform every check
in that exact execution order. RLS predicates match workspace identity for reads
and writes. Application code validates the person and establishes trusted context;
the current RLS policy does not independently evaluate individual staff membership,
roles or license assignments. Runtime connections must remain restricted and must
not own protected tables or have superuser/BYPASSRLS privileges.

Cross-record ownership constraints must remain valid: series/license, loan/borrower,
and release/loan references cannot cross workspace ownership. RLS is not a substitute
for those constraints or for permission checks on write actions.

RLS protects rows, not arbitrary media URLs, object storage, caches or exported
artifacts. Borrower profiles can be shared *within the organization* without making
their photographs publicly readable. Private-media serving needs its own verified
access boundary; opaque filenames alone are not authorization.

## Simpler onboarding direction

Use the product wording **Set up your business** and create the workspace through
the existing control-plane service as part of that guided journey. Guide the owner
through the first license, series, economic policies, product and borrower. Keep
revisiting setup straightforward. For one eligible license/series, preselect the
valid choice without bypassing validation or concealing which license a loan uses.
Do not fabricate license information or silently accept financial terms.

## References

- [Control-plane contracts](../architecture/control-plane-contracts.md)
- [Incremental delivery plan and role discussion](../plans/saas-access-media-and-onboarding.md)
- [AWS: tenant isolation](https://docs.aws.amazon.com/whitepapers/latest/saas-architecture-fundamentals/tenant-isolation.html): authentication/authorization and isolation are distinct responsibilities.
- [PostgreSQL: row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html): USING/WITH CHECK, privileged-role bypass, and row-local policy considerations.
