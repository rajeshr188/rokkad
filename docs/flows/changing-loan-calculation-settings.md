---
status: active
owner: project
updated: 2026-10-09
tags: [loans, setup, staff, ltv]
---

# Change loan calculation settings

An Owner or Admin can open **Loan setup → Calculation, fees and monitoring**.

1. The calculation form loads the current business default. To change a licence
   or series override, find its row in **Calculation policy history** and select **Use these
   settings**. Check the scope before saving.
2. Change the required value. For example, enter **0.95** for a maximum LTV of
   **95%**. Review the valuation method and effective start date. Leave the
   optional end date blank for an ongoing policy.
3. Review the gold/silver monthly rates and other settings, then select **Save
   calculation policy**. The configuration and both monthly rates save together.
4. The new version appears in history. You may save another version on the same
   date; the newest applicable date/version takes priority within its scope.
5. Retry the unsaved loan and review its calculation before approval/disbursal.
   A 95% limit still requires sufficient collateral value under the chosen
   valuation method; it does not guarantee that every requested amount qualifies.

Previously approved/disbursed loans keep their agreed calculation terms. New
drafts and approvals use settings applicable to their loan date. A new setting
dated today therefore does not change the policy applicable to an earlier loan
date. Existing series interest exceptions retain precedence: JSK WH remains
gold **1.1% per month** and silver **3% per month** unless its own override is
explicitly revised.

History is retained for review. An earlier row marked active remains eligible
for its dates, but the latest applicable date/version within the scope wins.
Changing calculation settings does not change fees or risk-monitoring thresholds.

When correcting a missing standing tenure for older paper loans, check the dated
rows in history. A revision starting 24 September does not replace a row starting
25 September, even if the 24 September revision was saved more recently. Select
**Use these settings** on the applicable 25 September row, supply the actual
standing tenure, retain its other settings and save with that same effective
start date. The added revision fills that interval; later effective policies and
existing loans' frozen agreements remain unchanged. Verify the boundary dates in
New loan. Use **Enter actual agreed terms** for a loan whose paper agreement
really differs from those standing defaults.

## Paper entry and monitoring setup

Select the series and original date before checking its standing setup. An
unselected series has not been checked and does not mean a policy is missing.
The paper form's current collateral valuation method and maximum LTV come from
the current **Calculation policy**, using series, licence and Workspace precedence.
An actual missing valuation setup links to that section. These settings do not
reapprove the original paper payout.

**Risk monitoring policy** separately supplies warning thresholds and evidence
freshness limits. If a policy already covers the scope and dates, do not add an
unlinked duplicate or change the date to evade the overlap check. In **Monitoring
policy history**, select **Amend** on the latest open-ended version, review the
settings and provide a reason. This creates an immutable successor; earlier
versions remain available. Merely selecting a series or opening either form
does not save a policy or consume a loan number.

For partial-month charging and the minimum full first month, see the
[interest policy guide](loan-interest-policies.md). A series calculation policy
takes priority over its license and Workspace defaults.
