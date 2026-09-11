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
| Routing, dashboard and module organization | R07/R11/R12 | R07 and R11 complete locally; R12 started: product-catalog, economic, license/series and print-profile setup extracted; remaining module families pending |
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
   routes and named aliases remain compatible. R12 module organization is next,
   product-catalog, economic, license/series and print-profile setup are extracted after checkpoint c9e27f9;
   document layout setup is next.


[Checkout flow and limitations](../flows/subscription-checkout.md) and
[decision](../adr/2026-09-09-workspace-checkout-evidence.md) describe completed billing
implementation. FW-002 remains an acceptance requirement before real paid onboarding,
not a blocker to this cleanup. Truly orphan/legacy contracts remain support cases;
no guessed contract restoration. No production deployment is authorized.
