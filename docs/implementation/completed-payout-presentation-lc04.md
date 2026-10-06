---
status: complete-local
owner: loans
updated: 2026-10-06
tags: [loans, admission, presentation, lc-04]
---

# One completed-payout action

LC-04 gives saved loans one visible **Record completed payout** action and one
canonical route. `completed_payout_adapter` describes the compatible review;
it is presentation, not posting authority. Existing authorized atomic commands
still recheck saved facts and source evidence under their locks.

## Adapter selection and compatibility

An unpaid DRAFT/APPROVED loan with no financial origin uses the existing paper
editor and recorded admission. A DRAFT with a matching genuine earlier native
approval instead uses its retained-native review. A fully reversed native payout
can use that same review after the existing reversal/reopen prerequisites.
Retained policy/quote identities, signed actor/date/digest, reason, setup/approval
authority and stale-evidence checks remain. No additional loan or financial origin
is created, and prior approvals, events, schedules and issued copies are retained.

An APPROVED unpaid loan can still use general completed entry with its genuine
approval retained and its original draft identity preserved. General completed
entry does not need an original digital quote or manufacture an approval.
Active origins and unsupported/dependent graphs remain servicing/correction cases.
Recorded/opening snapshots cannot enter the native reversed-origin adapter.

Old earlier-payout GET links redirect to the canonical action. Previously issued
v1 native reviews still POST at their original endpoint; signed reviews and
same-form retries keep their original command. Recorded intent submissions keep
the recorded command, including active/closed retries. Adapter selection never
falls back to a less restrictive command when a retained review fails.
Current lending retains its existing approval/price/LTV checks. No quote-age
change is included; the selected seven-day default remains LC-06.

## Explicit licence evidence mapping

New paper entry optionally selects an existing source licence revision in the
additional-details section. Preview/confirmation binds that mapping to the
request and freezes it in origination terms. The command checks Workspace,
series/licence ownership and original-date coverage. An inactive legacy reference
retains unknown original validity; it cannot authorize new lending.

The mapping is optional because recording known financial facts must not invent
licence evidence. With no mapping, ordinary admission/servicing remains supported
and bounded history/4 export still explains its missing-evidence blocker. With a
mapping, the existing flexible-history export can proceed if its other graph,
coverage and product prerequisites hold. No old loan is backfilled or converted.
A saved draft displays its original mapping disabled and preserves the existing
request shape, so previously issued recorded reviews/retries are not invalidated
by silently adding this new field. Direct origination is unchanged.

## Verification

Verification uses the existing disposable QA container and dedicated test database,
with restricted Workspace checks and synthetic source facts. All **257 affected
regression tests pass** (293.327s): general draft/current origination, genuine
approval/earlier payout, completed drafts and concurrent retries, source history,
paper entry, archive admission, history/4, exact recovery and real four-admission
continuation. All **18 final focused tests pass** (6.514s), including three further
form serialization, foreign-revision and native-reissue exclusion cases. Earlier
targeted fixture setup issues were corrected; no business regression failed.

The focused checks demonstrate read-only GETs, one visible action, old-link
redirects, retained approval/reversed payout evidence and original loan identity,
old/canonical POST retries, active-origin refusal, stale/withdrawn quote and actor
denial, setup/Workspace boundaries, truthful licence mapping/export, unknown
mapping/validity, frozen draft mapping and prior form request shape. Django system
checks, no migration drift, six template compilations, 41 changed/new Python parses
and whitespace checks pass. Logs remain private under `.tmp/lc04-20261006/`.

No migration, deployment, source-book acceptance, production conversion or
publication is included. Changes remain local and uncommitted; LC-05–07 remain.
