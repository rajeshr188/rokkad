---
status: implemented
owner: project
updated: 2026-10-17
tags: [loans, origination, setup, preferences]
related: [../adr/2026-10-17-business-lending-terms-and-entry-preferences.md, origination-complexity-review-20261017.md]
---

# Business lending terms: first two simplification steps

The owner accepted the complexity review's order and requested more detail on
number assignment. This local delivery implements the existing setup journey and
narrow change actions first. The owner confirms that staff print/share/write the
official number only after payout confirmation. The
[numbering proposal](loan-numbering-stage-proposal-20261017.md) explains the next
stage; no current allocation, loan identity or paper-number claim is changed here.

## Operator changes

The existing economic setup URL is presented as **Business lending terms**.
The effective view resolves the chosen register/licence and agreement date using
existing policy readers: rates and their source, charging rules, upfront interest,
tenure, fees, available repayment types, and prospective lending valuation/limit.
Today's initial entry preference is explicitly separate from the agreement date.
Current monitoring remains in its existing distinct section.

Choosing a scope in this view prefills that scope in the change actions and full
configuration form. Copying a particular saved configuration keeps its explicit
copy scope. Changes require preview/acknowledgment/confirmation through the existing
review service; no new wizard or policy-resolution algorithm is introduced.

- Rate-only changes append selected metals at Workspace/licence/register scope;
  blank metals retain their rules. They do not copy calculation or fee policies.
- Tenure/upfront-interest amendments copy the applicable calculation policy and
  replace only supplied fields. The review discloses that a narrower calculation
  policy is still a complete override, not per-field inheritance. Full initial
  setup and advanced overrides remain available in their existing form.
- Entry preferences have their own action. DIRECT/PAPER/INHERIT changes create no
  financial policy or metal-rate revision. They require no initial agreement/rate
  setup. The setting selects a screen, not loan authority or contractual terms.
- Fees retain their independent existing action; monitoring retains its separate
  reviewed policy amendment. The old two-metal form and configuration wire fields
  remain compatible with issued forms rather than creating competing routine UI.

## Independent entry preference

`LoanEntryPreference` is a small current-state model with direct Workspace
ownership, optional licence/register scope, purpose and updater/time. It uses
forced RLS, a unique scope with non-distinct nulls, explicit choice/scope checks,
and a database trigger rejecting cross-Workspace or mismatched register links.
The ordinary setup permission and Workspace lock apply. Preference audit retains
before/after scope values and actor. Identical confirmations retry without another
write; competing source-bound confirmations require fresh review.

Resolution remains register, then licence, then Workspace. At each scope an
explicit row takes precedence. Explicit INHERIT skips the legacy value at that
scope and follows broader settings; the ultimate fallback is DIRECT. With no
explicit row, the existing current effective financial-policy preference remains
the compatibility fallback. Migration creates an empty table: no deployed screen
preference, financial policy, loan or monitoring row is rewritten.

New setup review tokens bind the preference state too. Earlier configuration
reviews retain their previous financial-state comparison when no independent
preference has subsequently been written; otherwise they require a fresh review.
Loan agreement-review fingerprints are unchanged because changing entry preference
does not create another financial policy identity.

The existing policy-default reader is also used for the initial mode of an
ordinary repayment form. That reader retains its legacy behaviour. New loan
presentation and the effective setup summary use the independent preference
reader, so changing the new setting cannot silently select a repayment mode.
Explicit closing mode remains unaffected.

## Persistence, portability and release boundary

Loans migration **0093** creates the isolated preference table and guards.
`data_portability` **0032** admits package profile **5**. Setup/package profiles
1–4 keep their exact fields and meanings; exports with independent preferences
require version 5 instead of dropping them. Version 5 adds the explicit published
preference inventory and remaps licence/register references through existing setup
restore. Old packages remain readable. Restored licences still require ordinary
destination review; an entry preference cannot enable lending.

Native ordinary-Loans recovery includes the preference rows, actor and identities
under its existing exact-schema/guard contract. Older exact archives still require
their matching application/database boundary; this is not a schema-upgrading
recovery adapter. No servicing-bundle or saved economic contract changes.
See the [version-5 setup contract](../contracts/fresh-business-setup-v5.md).

This is an additive schema/application release. Web, commands and workers must
share the compatible migrated application. A later deployment needs normal backup,
migration and exact-source acceptance; this local task does not deploy or change
production setup. New profile-5 receipts prevent reverting their profile support.

## Verification

The final combined acceptance run passes **173 tests in 142.789 seconds** on the
fresh local database: setup changes, preference isolation, concurrent confirmation/
retry, earlier configuration reviews, origination/closing, native recovery,
package profiles, registry and onboarding. Two included browser tests cover
**30 desktop/mobile page checks** (12 lending setup and 18 existing origination),
with no page exceptions or horizontal overflow. The saved-draft integration check
confirms unchanged loan/number identity and financial review after an independent
entry-preference change. A separate 31-test compatibility run covers repayments,
shared origination/closing, preference package round trip and the final UI.

Ruff, Black on 27 changed/new Python files, migration-drift checking with owner-only
settings, 2,699 documentation links across 778 files, all 22 document originals,
supported app boundaries, repository hygiene and diff whitespace pass. The Hindi
heading catalog is updated and compiled. Logs are in ignored
`.tmp/lending-setup-acceptance.log` and `.tmp/lending-preference-compatibility.log`;
fictional browser evidence is in `outputs/lending-setup-20261017/` and the existing
origination artifact directory. No production data or credentials are in these artifacts.

The reused test database had lost migration-seeded roles after transaction tests;
fresh migrations restored that fixture baseline without changing application code.
A preexisting onboarding test expected immediate configuration save despite the
already-required review in the deployed baseline. It now verifies read-only
preview, explicit confirmation, return-to-setup and no billing/financial event.

Formatting-only baselines for existing files are retained separately in ignored
`.tmp/lending-formatting-only.patch` and `.tmp/lending-test-formatting-only.patch`,
with AST equivalence checked. Source behavior can be reviewed against
`.tmp/lending-format-baseline/`. Root WhatsApp work and earlier pending closing/
search implementation remain preserved in their existing worktrees/checkpoints.
