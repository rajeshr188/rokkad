---
status: active
owner: project
updated: 2026-09-11
tags: [plans, saas, hardening]
related: [../architecture/2026-09-09-project-review.md, future-work.md]
---

# Incremental project hardening

The owner approved proceeding with the recommendations. Deliver bounded checkpoints
in the order below; the [review](../architecture/2026-09-09-project-review.md) holds
the evidence and acceptance criteria. This plan does not reactivate FW-001 license
scoping or authorize production deployment.

| Increment | Findings | Status |
| --- | --- | --- |
| Reproducible foundation | R01/R02 and R06 runtime-role gate | Implemented; validation recorded in STATUS |
| Operational commands | R05 | Implemented; validation recorded in STATUS |
| Paid billing correctness | R03/R04 | Checkout binding, replay, invoice and webhook repair implemented; expiry implemented; known-payment/refund recovery implemented; owner review decisions implemented; provider acceptance shelved as FW-002 |
| Current docs/product/residue cleanup | R08/R09/R10, verified R13 | R08/R09/R10/R13 complete; bounded removal evidence linked below |
| Routing, dashboard and module organization | R07/R11/R12 | R07 and R11 complete locally; Loans views portion of R12 complete; orgs workspace/role settings extracted; team/invitations extracted; orgs views complete including account/preferences and slug adapters; broader model/form/renewal review separate |
| Production operations acceptance | Remaining R06 | Pending selected deployment; no live deployment requested |

Foundation implementation and operator commands are documented in
[Containers and CI](../implementation/container-and-ci.md) and
[Loans operator commands](../implementation/loans-operator-commands.md). Existing migrations,
action grants, protected files and historical compatibility routes remain intact.

## Current delivery priority

The owner shelved Razorpay setup/provider testing as
[FW-002](future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance).
No Razorpay setup is needed for the remaining review cleanup. Resume delivery with:

1. R08 completed: current index, dependency/testing policy and context rewritten;
   original context retained in linked archives. Current-entry link check runs in CI.
2. R09/R10 completed: current tour choices preserve historical answers; removed six
   definition-only settings and replaced the DEA guard with tracked-source AST checks.
3. R13 completed: four unused direct packages and 14 unreachable templates removed;
   [reachability and retention evidence](../implementation/dependency-template-cleanup.md).
4. R11 visibility, batching and [query measurements](../implementation/dashboard-reliability.md) complete.
   R07 is complete: all 136 canonical Loans routes use direct Workspace adapters;
   all URL generation is scoped and response rewriting is removed. Old mapped-domain
   routes and named aliases remain compatible. The Loans views portion of R12 is
   complete: all handlers live in focused web modules, with public imports retained.
   See [module map](../implementation/loans-view-organization.md). Broader R12
   orgs workspace/role settings and access helpers are now extracted. Team and
   invitations are also extracted; orgs view organization is now complete, including account/preferences and slug adapters; see the [orgs module map](../implementation/orgs-view-organization.md).
   The remaining-module review below selects the next bounded increment.

## Remaining R12 module review

Reviewed after publishing orgs checkpoint `38eb1e3`; no application code changed
during this review. File size is supporting context, not a reason by itself to split.

| Candidate | Evidence and recommendation |
| --- | --- |
| Loans forms | `forms.py` mixes document layout/overlay/print-profile editing, license setup, funding, pawn intake, custody and lifecycle inputs. Its first 13 classes form a coherent document-editing group (lines 36–414), with an internal print-profile inheritance relationship. Extract this group first into a focused web form module, retaining public imports from `loans.forms`. |
| Core models | `models/core.py` mixes numbering/economic policies, loan/collateral records, immutable evidence, releases, auctions and renewals. The existing model package already separates other features. Defer moving these classes until a concrete change benefits from it; preserve Django model identity, relationships, constraints, default-callable paths and public imports, with no generated schema migration for organization alone. |
| Renewal service | `services/pawn_renewals.py` contains previews, atomic execution/reversal, fingerprints and shared validation. Execution and reversal depend on row locking, replay handling, custody evidence and compensating events. Keep the transaction orchestration together for now; a later preview/helper extraction needs explicit dependency mapping and renewal/reversal regression coverage. |

The document form increment is implemented locally: 13 classes now live in
`web/document_forms.py`; `forms.py` retains public imports and the two document
setup handlers use the owning module. All 50 form class bodies remain unchanged.
The three license/series setup forms are also extracted into `web/license_forms.py`
with compatible public imports and unchanged class bodies. License setup handlers
use the owning module. Next: verify publication CI and review remaining form
families before choosing another extraction.
Core model and renewal-service moves remain deferred.

Each form increment must preserve fields, validation, widgets, constructor
arguments and public class identities. Inspect callers and mock targets, compare
class bodies, then run existing document-layout/print-profile and affected web
tests plus import checks. Do not introduce a generic form framework or change
document behavior as part of the move. Remaining form families can follow only
where they offer similarly coherent boundaries.



[Checkout flow and limitations](../flows/subscription-checkout.md) and
[decision](../adr/2026-09-09-workspace-checkout-evidence.md) describe completed billing
implementation. FW-002 remains an acceptance requirement before real paid onboarding,
not a blocker to this cleanup. Truly orphan/legacy contracts remain support cases;
no guessed contract restoration. No production deployment is authorized.
