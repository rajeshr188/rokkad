---
status: accepted
owner: project
updated: 2026-10-05
tags: [adr, loans, source-history, portability]
related: [2026-10-05-unified-loan-admission-and-continuation.md, ../contracts/loan-history-v4.md]
---

# Recorded source history without retrospective approval

The owner authorized LD-05 after the shared contract and reduced-principal
checkpoint slices. New `loan-history/4` admits a complete supported source
agreement through the existing recorded-origination, repayment and full-release
writers. It does not create another loan model or a past digital approval.
Published history/1, /2 and /3 retain their strict native calculation, valuation,
approval and allocation requirements.

The bounded agreement is simple full-month flexible repayment, the shared original
anniversary calendar, captured per-item/per-period HALF_UP rounding (paise or whole
rupees), original item principal/rates, zero or one upfront month, and an identified
fully deducted document charge. Actual receipt amounts, interest/principal/fee
splits and item before/applied/after amounts must reconcile. Import never replaces
an actual lower-rate-item reduction with native highest-rate-first allocation.
Unsupported source rules need retained evidence and a reviewed opening or wider
profile; incorrect arithmetic is a historical inconsistency, not an exception.

A compatible ACTIVE or RETIRED destination product supplies future servicing
semantics. Its availability dates are not evidence of the historical lending
decision in this new profile. Source calculation identity, tenor, grace and product
structure must still match. Original licence validity is verified or explicitly
unknown under an inactive legacy reference. Current issuance guards remain intact.
Current monitoring policy is selected separately; missing original valuation stays
unknown and no current appraisal is invented.

Reuse immutable `HistoricalLoanImport` JSON and source bindings for aliases. A
source ID is unique within its namespace, including a book discriminator for
book-local IDs; existing legacy schema scoping is unchanged. Same original number
in different books is permitted, with distinct generated local numbers and
searchable source book/number. Same book/number with a different source ID is held.
Numbers and documents already issued are not rewritten, and live numbering ranges
remain reserved. Company locks, source uniqueness, exact Party resolution and
immutable batch confirmation protect admission and retries.

Export/restore accompanies this writer. Original claims, purpose and known handover
time remain in the portable source document, independently of the local importing
actor. Restoration records completed facts on their actual dates; it does not claim
a transaction is being performed again or that an unknown handover time is known.
Interest recognition is derived and checked against the frozen shared agreement;
it is not disguised as an independently supplied paper cash transaction.

Full-history export requires verified source-book coverage through its cutover and
rejects unsupported operations and custody/funding/storage graphs. It is bounded
financial portability, not exact-identity recovery or a binary/document backup.
No automatic archive conversion, old-cohort correction or deployment is authorized
by this slice. Remaining operation and capture-transition work is LD-06; wider
portability and rollout remain LD-07/08.
