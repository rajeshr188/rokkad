---
status: accepted
owner: loans
updated: 2026-09-12
tags: [loans, rates, origination, evidence]
---

# ADR: Same-day origination quotes and frozen approval provenance

The owner selected same-day quotes at approval, then authorized implementation
of the [origination review](../implementation/origination-rate-freshness-review.md).
The initial implementation uses the recommended current-day loan/disbursal scope;
this is an implementation assumption, not a separately confirmed owner preference
about historical entry. Historical entry requires a separate contract.

## Decision

- Calculated-metal and lower-of valuations require a positive applicable same-day
  INR pure-metal buying quote for every consumed metal. Use the configured local
  calendar date and exclude future-effective quotes, including later today.
  Loan and disbursal dates must be today for those methods. Appraisal-only
  valuation retains existing appraisal/date behavior and needs no market quote.
- Draft saving keeps its existing availability and financial validation. A stale
  but available quote can support draft preparation; approval requires fresh
  evidence. Missing-price draft validation is not removed. HTMX shows the
  difference and preserves the another-tab Rates/check-again recovery path.
- Approval freezes quote identity, Workspace, metal, currency, purity, per-gram
  buying price, effective/recorded times, source identity/snapshot and quote author.
  It also records the rule version, valuation method, loan date and evaluation
  time. Calculations consume these same selected quotes. Existing JSON approval
  evidence and its immutability protections are reused; no new table is needed.
- Legacy drafts with no item allocations use the existing fallback valuation
  policy and must also satisfy its quote requirement. Missing itemization must
  not bypass the new rule. No historical quote identity is inferred for an old
  approval that lacks evidence.
- Disbursal validates the frozen quote evidence against the latest applicable
  same-day selection and preserves approved monetary values. An old approval,
  correction, withdrawal or replacement requires return to draft and a new
  approval. Equal-price replacement still changes the evidence identity.
  Existing approved appraisal-only economics remain usable without market evidence.
- Simple review binds quote identities as well as economics in its signed review.
  Changes during confirmation roll back approval and disbursal together. Renewal
  preview/confirmation includes quote evidence in its fingerprint, and successor
  activation checks it too; renewal has its own activation path.
- Selection and eligibility are checked again at the decision boundary. Changes
  visible at that check require review. This does not serialize all Workspace
  quote entry: a quote arriving after the decision is a subsequent market change,
  and never rewrites completed evidence. Monitoring handles later market changes.
- Existing permissions and explicit Workspace/RLS context remain authoritative.
  No new override permission, owner bypass or license access restriction is added.
  Completed-action replay still checks authorization before returning its original
  result; it does not run a new quote-age gate. Repayment, release, reversal and
  closed-loan evidence remain unchanged.

## Consequences

An approved market-valued loan awaiting disbursal may need a new loan date,
reviewed terms and another approval after day rollover. The original approval
remains in history. Operators can follow Rates and return-to-draft links; staff
without editing/approval grants must involve an authorized reviewer.

This rule is separate from active-loan monitoring freshness. It neither changes
monitoring intervals nor resumes the shelved [capacity test](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).
There is no migration, rate feed, Redis dependency or automatic worker startup.
