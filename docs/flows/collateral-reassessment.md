---
status: active
owner: loans
updated: 2026-09-11
tags: [loans, collateral, appraisal, operator]
---

# Review collateral value on an active loan

Open the loan and inspect **Current collateral valuation**. It separates the metal
estimate, approved staff appraisal, and policy-selected value. Each evidence date,
age and freshness status is shown. The effective monitoring policy sets maximum
ages (initial defaults: seven days for prices and ninety for appraisals).

The last allowed day is included. Zero requires same-day evidence. Lower-of
valuation requires both a fresh price and appraisal. An appraisal-only policy does
not need a fresh price, and a calculated-only policy does not need a fresh appraisal.
Stale or missing required evidence makes coverage **Unknown**, not safe or zero.
Refresh the missing evidence before relying on a coverage result.

To record a new staff appraisal:

1. Under the held collateral item, select **Reassess / history**.
2. Review the item details, price reference/date, existing photos on the loan,
   and prior appraisals. A market estimate is not a substitute for inspecting
   condition or reviewing an external appraisal report.
3. Enter the independently reviewed INR value. Choose **Physical inspection** or
   **External appraisal report**, and record a supporting reference and reason.
4. Select **Approve new appraisal**. It takes effect now, creates a new version,
   records the reviewer and preserves the earlier record. Reference quote context
   is captured again at recording; it may have changed since the page was opened.
5. The loan detail recalculates current coverage. Its saved risk assessment is
   marked stale until refreshed. Original loan terms and amounts remain unchanged.

Recording requires permissions to view/edit data and approve loans. View-only
members can use **Appraisal history**. A closed loan or collateral no longer held
cannot be reassessed. If another review was saved while the form was open, reload
and review the latest version before submitting again.

Use another reviewed version to correct an appraisal. Do not edit the draft's old
appraisal value, backdate evidence, or delete history. This workflow records a
supporting reference and notes; external-report file upload is not included.

Freshness here applies to current monitoring. New-loan quote availability checks
do not yet enforce an origination-age policy. Time-based refresh of saved portfolio
assessments remains the next increment; a saved assessment is not a live market feed.
See [metal prices](metal-rate-entry.md) and the
[freshness decision](../adr/2026-09-11-collateral-freshness-and-reappraisal.md).
