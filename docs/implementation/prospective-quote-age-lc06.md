---
status: implemented
owner: loans
updated: 2026-10-06
tags: [loans, rates, implementation, lc06]
---

# LC-06: prospective quote age

Workspace owners can set **Loans setup → Loan entry → Buying quotes for new
lending → Maximum buying-quote age**. The default is seven inclusive calendar
days. Zero requests same-day quotes. Setup administrators can see the limit and
continue managing photos, but cannot change the lending-age limit.

The shared prospective quote selector retains the Rates facade's deterministic
latest applicable source/version selection. Draft price readiness and the item
LTV hint use the same age boundary as approval. They show the quote's source,
identity, effective date and age; missing/expired prices keep the Rates and
Recheck recovery path. An unchanged eligible price does not require an invented
new daily confirmation. The valuation-review comparison and approval detail
show applied limits and quote ages; approved ages are frozen evaluation facts.

`LoanOriginationSettings.maximum_quote_age_days` defaults to 7, with a 0–32767
storage range. The setter uses active Workspace authorization, the canonical
owner capability, business-write availability, the existing Workspace lock and
`PreferenceAuditLog`. Missing-row reads do not write; zero is distinct from
missing. Migration 0063 adds the field and upper bound to the existing forced-RLS
table. No registry/table expansion is necessary.

New approvals use `quote-age-origination-v2`, freezing the applied maximum,
calendar basis and ages outside unchanged quote identity dictionaries. Approval
and payout recheck identities, current configuration and age eligibility, with
rollback on intervening changes. Signed simple, renewal and updated-valuation
reviews bind the limit without binding volatile evaluation timestamps. Current
loan/payout dates remain explicit; delayed approval cannot silently move the
interest anchor. Completed retries retain original evidence and authorization.

Legacy same-day approvals retain their original rule and checks. Retained-native
historical recording bypasses the current prospective age contract through its
existing historical adapter. General paper admission, opening/history imports,
closed archives, servicing economics and monitoring policy are unchanged. Khata
prospective reviews also bind the new limit; legacy pending opening approvals
without it need another review before first payout. Native recovery preserves
the new setting under its existing matching-schema requirement.

## Verification

The complete affected run passes **143 tests** (59.478s), covering quote
eligibility, owner setup, appraisal/readiness guidance, updated valuation and
Khata opening. The broader **480-test run passes 477** (431.644s). A PostgreSQL
recovery test deadlocked; two obsolete fixtures still assumed one-day expiry or
created an ACTIVE loan with no financial origin. The expiry now uses eight days;
the UI fixture uses real approval/disbursal. No command guard was relaxed.

All **52 follow-up tests pass** (33.575s), including those three cases, all 23 new
quote-age checks, two new Khata cases and exact recovery with a non-default owner
limit. All **25 final checks pass** (8.314s), including final legacy-limit display.
Selected checks pass across runs; this is not one clean 480-test rerun. Django
checks, no migration drift, all six LC-06 templates, 104 changed/new Python parses,
runtime JSON inventories and whitespace checks pass.

Migration 0063 was generated through ordinary Django owner settings and applied
only in disposable PostgreSQL QA. No local user database or production database
was migrated. Private logs are under `.tmp/lc06-20261006/`. Code and documentation
remain local and uncommitted with the preceding LC slices.

The next slice is **LC-07 release acceptance**: production cohort inventory, real
source/staff acceptance, recovery/deployment rehearsal and release gates. LC-06
does not include publication, production deployment or archive conversion.
