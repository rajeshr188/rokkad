---
status: accepted
owner: project
updated: 2026-10-03
tags: [loans, paper-entry, renewal, custody]
---

# Independent paper loans and renewal through ordinary servicing

The owner clarified that Lakshmi records each paper loan independently. Staff
may know that a numbered loan closed without knowing whether another agreement
followed it. Reconstructing a predecessor/successor chain is not a prerequisite
for recording that loan. Once a loan is entered, a known renewal may use ordinary
Renew and preserve the relationship. This supersedes the compulsory-chain
interpretation of the [unified recording decision](2026-10-02-unified-loan-recording.md),
without rewriting earlier retained evidence.

## Decision

Make one paper loan the primary unit of entry. Its terms, receipts and closure may
be entered together or serviced later. The checked-through date covers that loan's
known records; it does not attest to an unknown earlier/later loan. Initial linked
history entry remains an optional existing capability, not a migration requirement.

Separate agreed debt, paper proceeds after deductions, closing settlement amounts
and confirmed physical cash. New paper entry identifies CASH or PROCEEDS. PROCEEDS
retains the ordinary net-disbursed contract amount and explicitly leaves actual
physical cash unknown. The existing event's legacy `net_cash` field is contract
proceeds for this identified basis, not an attested physical payout. Read models,
reviews and documents must expose that distinction. No second cash ledger is added.

Allow a fully deducted, identified document charge and zero/one advance-interest
month. Charges already deducted do not become outstanding fees or collectible
first-month interest again. Preserve the actual terms without original digital
approval, quotes or valuation checks. Current collateral assessment remains separate.

A paper closing settlement may fully extinguish debt without asserting cash
collection or customer handover. The new PAPER_CLOSED custody value means the
closed paper record does not establish physical customer handover. It is not an
eligible active pledge. Preserve last-known storage evidence; do not fabricate a
storage removal or handover time. Source-based uncertainty remains visible in
reconciliation, documents and reports. Confirmed full returns keep existing meaning.

On an active entered paper loan, ordinary Renew offers perform now and record a
known completed paper renewal. Perform now settles the source using its agreed
anniversary balance, then applies ordinary current policy, prices, appraisal, LTV,
photo requirements and approval to the new decision. The paper monitoring policy
does not become the new origination policy. Source interest is recognized once
and only supported scheduled interest capacity is allocated.
Ordinary paired reversal of that current renewal restores its source and custody
without reversing the original paper origination. Already-completed paper renewal
continues to require supported history correction.

Known completed paper renewal uses its actual date, original new number and agreed
terms. No original price or digital approval is invented. The current supported
case retains one collateral group in business custody, relabelled for the new loan.
Financial settlement/opening and custody lineage use the existing renewal records.
Staff do not need to reconstruct any earlier chain. Cash is recorded after netting
the old settlement and new deductions; no new payout or historical reminder occurs.

For old principal 10,000 and old interest 200, new principal 12,000, new advance
interest 240 and document charge 10, net payout is **1,550**. Old debt is settled,
new principal is 12,000 and the new first month is credited. Principal reduction
and unchanged-principal cases use the same formula. Unpaid interest is not silently
waived or capitalized.

## Integrity and boundaries

Signed review binds actor, Workspace, source financial fingerprint and normalized
facts. Lock the source loan, rerun the existing canonical writers and commit
atomically. Exact retries return the same result; different facts on the same
submission fail. Earlier closure/renewal cannot silently precede existing later
financial or custody activity. Known closed paper settlements may use the existing
unchanged-agreement receipt correction command, retaining their uncertainty.

The initial chain profile retains its earlier bounded scope; complex historical
chain reconstruction is deprioritized. This change does not enable interest
capitalization/concessions in paper entry, arbitrary contract/date/custody amendments,
auction recovery or imported-opening renewal. Recorded-origin restorable portability
remains separate remaining work. Existing operational PostgreSQL backup and ordinary
report exports are not replaced by this feature.

Recorded contract copies use their immutable origin event; current interest-position
copies bind the financial fingerprint, transaction-coverage review and business date.
Serialize projection and issuance under the scoped loan lock. Preserve issued bytes and
the actual generation time. Native tickets and schedules retain existing behavior.

Implementation and verification are local; migration 0045 and deployment are pending.
See the [plan](../plans/unified-loan-recording.md) and
[workflow](../flows/unified-loan-recording.md).
