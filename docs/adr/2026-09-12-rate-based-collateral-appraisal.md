---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, rates, appraisal, migration]
---

# Reviewed rate-based collateral appraisals

The owner requested current Rates-based valuations when migrating the old loans,
then supplied and approved the test gold quote. Reuse the Loans appraisal service
and immutable appraisal model. Add RATE_BASED alongside physical inspection and
external report, without implying inspection or changing loan financial origins.
This extends the allowed methods in the
[freshness decision](2026-09-11-collateral-freshness-and-reappraisal.md).

For RATE_BASED, require the reviewed quote ID and an exact value equal to pure-metal
INR buying price times net grams times purity / 100, rounded down to paise. Require
the current applicable monitoring policy and its price freshness limit. Missing or
stale prices, a changed quote, or a submitted value differing from the calculation
fail before writing. Existing actor, Workspace, custody, active-loan and appraisal
version checks remain. Inspection/report appraisals still allow an independently
reviewed value.

Append a current-time appraisal carrying method, reviewer, supporting reference,
review reason, weight, purity, price, quote ID/effective time, calculation and price
age limit. Preserve prior appraisals and accepted import evidence. Mark any saved
risk snapshot stale through the existing service. The frozen loan policy remains
unchanged; LATEST_APPRAISAL can select this reviewed rate-based value. A later price
does not rewrite the saved appraisal; its configured appraisal-age limit applies.

The one-time migration operator can compose opening import with this ordinary
current-date appraisal action after reviewing the quote and recorded collateral
facts. A historical cutover must not backdate a present-day appraisal. This change
does not add a dump-specific appraisal model, direct adapter writes, a bulk command
or automatic appraisal creation to generic imports. Missing weights/purity/rates
remain explicit exceptions. Source verification and financial balance approval
remain separate from approval of a current valuation.

Opening export/restore retain method and frozen source quote context; a restored
quote ID is labelled with its source Workspace rather than rebound to a local rate.
