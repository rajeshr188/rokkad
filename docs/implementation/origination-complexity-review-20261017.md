---
status: accepted
owner: project
updated: 2026-10-17
tags: [loans, origination, architecture, simplicity, review]
related: [loan-origination-friction-review-20261017.md, origination-simplification-20261017.md, ../domain/loans-regulatory-setup-and-policy.md]
---

# Origination complexity: necessary rules and avoidable coupling

## Scope and conclusion

Owner-requested source review of the maintained loan-workflow worktree at
`ccd5f5e4`, including the separately pending navigation/search changes. No live
configuration, usage counts, timings or frequency of operator mistakes were
queried. Findings distinguish observed code from design judgments. This is a
review accepted by the owner. The [first two implementation steps](business-lending-terms-20261017.md)
are local; the subsequently approved [numbering stage](loan-numbering-stage-proposal-20261017.md)
and bounded paper-reference refinement are tracked in the
[remaining implementation](approval-numbering-20261017.md). The findings below
retain the pre-change source baseline and reasoning.

The primary simplification opportunity is composing and changing standing setup,
not removing automatic numbering or immutable saved agreements. Early permanent
number allocation is a separate, real source of draft-recovery complexity.
Recent improvements explain resolved terms and provide safe recovery; they do
not remove the underlying setup hierarchy or reservation timing.

## Findings and evidence

| Area | Observed behavior | Assessment |
| --- | --- | --- |
| Automatic numbers | A row-locked counter per register/document kind; read-only previews; committed numbers never recycled. | Necessary for concurrent new lending and historical backfill. Keep. |
| Number assignment stage | Draft construction allocates permanently. New-loan Review saves that draft before redirecting to agreement review; saved draft register/product are fixed. | Real tradeoff: a pre-payout scope mistake needs a linked replacement, even though money has not moved. Review this stage separately. |
| Standing agreement setup | Calculation policy resolves series, licence, then Workspace by date/revision; metal rates resolve independently; fees resolve separately by code at licence/Workspace scope. | Legitimate variation, but too much implicit composition for routine setup and troubleshooting. Highest simplification priority. |
| Override meaning | A series calculation policy replaces the full broader calculation policy; entry purpose has its own INHERIT behavior; a series rate changes a metal's rate independently. | Different meanings of override create surprise. Prefer narrow existing rate actions and show the effective result. Do not add generic per-field inheritance without a concrete need. |
| Entry preference | DIRECT/PAPER preference is stored on the financial calculation policy. The complete configuration writer also requires at least one metal rate and appends policy/rate rows. | Concrete responsibility coupling: a screen preference should not require the operator to perform a financial setup amendment. |
| Product catalog | Four standard draft products are intentionally prepared. Their versions describe repayment/obligation behavior; the only available direct product is already selected and compacted. | Do not call the catalog unused or delete it without usage evidence. Routine setup should emphasize the business's selected repayment type, with others secondary. |
| Saved agreement | Approval/recorded admission retains actual calculation terms, source references and product evidence. Later setup does not change an active loan. | Necessary contract evidence, distinct from reusable defaults. Preserve. |
| Paper valuation reference | Paper standing terms also resolve today's economic policy for a saved valuation fallback/reference; current monitoring resolves a separate effective monitoring policy. | Remaining compatibility seam. Keep historical references truthful, while keeping routine risk configuration out of paper agreement entry. Removing fields requires contract/read-model review. |
| Workflow controls | SIMPLE owner mode already confirms approval/payout together; EXTENDED retains separate authority. | Keep the simple operational route. Different permissions and actual historical payout evidence cannot be removed as mere UI duplication. |

Source map:

- `services/number_allocation.py`: atomic allocation and non-consuming preview.
- `services/license_series.py:reserve_sequence_through` and
  `services/recorded_numbers.py:claim_number`: reserved historical ranges, duplicate
  evidence, and protecting live counters during original-number admission.
- `services/pawn_drafts.py:_create_pawn_draft`,
  `web/pawn_draft_actions.py:_draft_submission_redirect`, and
  `forms.py:PawnDraftForm`: reservation before final review and fixed draft scope.
- `services/economic_policies.py`: separate calculation, metal-rate and fee
  resolution; complete configuration writes.
- `services/entry_purpose.py`, `web/economic_forms.py`: operational preference
  stored and edited with economic setup.
- `models/products.py`, `services/product_catalog.py`,
  `web/direct_entry_layout.py`: intentional product capability and existing
  single-choice simplification.
- `services/paper_entry_terms.py`, `services/recorded_history.py`,
  `selectors/monitoring_policy.py`: original terms, retained references and current
  monitoring have separate meanings.

The source paths above are relative to `apps/tenant_apps/loans/`. Existing
decisions on numbering, product/obligation evidence, shared origination and safe
draft replacement remain authoritative until a new decision is approved.

## A simpler operating model

Give administrators one coherent presentation of **Business lending terms**:
the offered repayment type, metal rates, monthly charging rule, upfront interest,
document charge, tenure and prospective valuation/lending limit. Use the existing
policy writers and resolvers. Present real licence/register differences as
exceptions, showing the effective values for the selected date and what each
change affects. No new LoanProgram table, rule engine or workflow framework is
needed to achieve this presentation.

Keep four responsibilities visible and separate:

1. Licence/register identifies the business authority and number book.
2. Standing terms suggest the agreement; the reviewed saved agreement determines
   the loan's contractual obligations.
3. Entry preference selects the initial screen purpose and never changes terms.
4. Current monitoring assesses canonical debt and collateral under its own policy.

For example, licence A/register AA can reserve the actual prior range through
AA05000, issue new direct loans from AA05001, and admit unused original paper
numbers AA00001 through AA05000 later. The reservation covers all used source
numbers, including closed/excluded loans. Backfill must still reject duplicates
and retain actual historical terms; it does not rewind the live counter or inherit
today's agreement as historical truth.

## Recommended order

1. Simplify the existing setup journey around business terms and explicit
   register exceptions. Preserve the already implemented effective-term summary,
   amendment review and single-option selection; do not add another wizard or
   confirmation layer. Keep advanced rules accessible where actually used.
2. Provide narrow change actions for entry preference and agreement fields.
   Extend the existing rate-only pattern where justified, so changing one concern
   does not require the operator to understand a complete policy replacement.
   Any entry-preference storage separation must retain its scoped behavior,
   history, portability and open-form compatibility; do not add a generic settings
   system or silently rewrite old snapshots.
3. Evaluate unnumbered review before permanent reservation. The current Review
   action crosses that boundary early. First establish whether the business treats
   a saved draft number as issued and whether draft printing/references depend on
   it. Prefer review of entered facts before allocation if the business permits;
   existing numbered drafts retain their numbers and recovery path. This changes
   signed reviews, retry identity and persistence assumptions, so needs a separate
   ADR, migration/compatibility design and targeted concurrency/recovery tests.
4. Reduce the paper reference/monitoring setup seam where existing evidence
   contracts permit. Retain known saved references, explicit unknowns and current
   monitoring policy independence. Do not fabricate original appraisal or approval.

Before retiring product variants or changing draft issuance, gather scoped
aggregate evidence of actual enabled/used products, issued draft documents and
wrong-register replacement frequency. No production query or change is authorized
or performed by this review.

## Boundaries and acceptance

Do not merge standing defaults, immutable agreements and monitoring into one
mutable policy. Do not remove original-number collision checks, source/custody
evidence, posted correction boundaries, tenant authority or idempotency. Existing
monthly paper agreements and saved direct started-week agreements retain their
actual rules and supported correction limits.

Any implementation should demonstrate routine entry without policy-ID knowledge,
predictable narrow amendments, unchanged saved agreements, concurrent numbering
and paper backfill parity, supported corrections/portability, and unchanged
monitoring outputs for identical financial/evidence inputs. Simplification is
successful when operators make fewer technical choices without weakening these
contracts; fewer tables or shorter files alone do not establish that.

No application behavior or production data changes in this review. Financial
tests are not rerun for documentation-only analysis. Existing pending navigation/
search validation remains its own checkpoint.
