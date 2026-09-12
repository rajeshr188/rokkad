---
status: active
owner: loans
updated: 2026-09-12
tags: [loans, monitoring, operations]
---

# Review loan health and change monitoring limits

Open **Loan setup → Operations console → Loan health**. This remains an
administration screen requiring workspace settings permission. Every active loan
appears, including loans that have never been assessed. Loan detail remains the
place for live calculations on active loans and collateral appraisal history.
Closed loans stop live health calculations and disappear from active alerts;
settlement, appraisal and event history remain available. A release reversal that
reopens a loan puts it back into monitoring with an outdated assessment.

## Read the portfolio

- **UNASSESSED:** no saved assessment exists. Use Refresh.
- **STALE:** the date, calculation contract or source evidence changed. Refresh
  before using the amounts. Yesterday's assessment is outdated even if nobody
  edited the loan.
- **ERROR:** an assessment failed. Open the loan, correct the reported setup or
  evidence problem, then refresh.
- **CURRENT:** calculation succeeded for today using the current rules. This is
  assessment freshness, not a declaration that the loan is healthy.

Repayment performance shows days past due, due now and overdue amounts. Collateral
coverage separately shows eligible value, LTV, full shortfall and policy headroom.
A payment-current loan can have a collateral shortfall; an overdue loan can still
have enough collateral. These labels do not introduce a regulatory NPA judgment.

Each loan labels its coverage exposure as **Maturity payoff** for bullet/flexible
loans or **Economic exposure** for amortizing loans. The separate economic-exposure amount is not
necessarily the same number. Full shortfall compares coverage exposure with full
eligible value; policy headroom compares it with the permitted portion of value.
Negative headroom can arise before full shortfall. No per-item debt allocation is
invented by this screen.

Expand **Prices and appraisals** to see each item's evidence dates, status and
reasons for unknown coverage. Refresh uses recorded evidence; it does not make an
old quote or appraisal new. Enter an updated quote through
[Rates](metal-rate-entry.md), or use the authorized
[collateral reassessment](collateral-reassessment.md) workflow as needed.

Summary totals show **Unavailable** while any active loan lacks a current monetary
assessment. The counts explain the missing work. Unknown coverage has a separate
count among current assessments. Metric filters use current results only. Internal
alerts retain their assessment dates; review live details before acting. Nothing
is sent to a borrower merely by opening or refreshing this page.

## When a loan needs another assessment

Refresh health after relevant source changes: repayments or their reversals,
collateral/custody/appraisal changes, applicable metal quotes (including corrections
or withdrawals), and monitoring-policy changes. A newly active or reopened loan
also needs an assessment. Closed loans leave the monitoring queue.

Refresh active loans once each new local calendar day even without an edit: DPD,
maturity distance, projected interest and evidence freshness can change with time.
The repeating worker selects missing, outdated or failed assessments; it does not
recalculate every already-current loan every minute or every hour. Its busy/idle
polling intervals control when pending work is noticed, not the lifetime of a
successful assessment. An authorized individual refresh remains available.

The owner selected completion within one hour after an applicable metal-price
change as the launch load-test target. That does not mean all active loans need
hourly recomputation when nothing changes. Automatic calculation refresh is also
different from physically inspecting collateral and recording a new appraisal.
Refreshing cannot cure stale or missing price/appraisal evidence.

## Payment performance and the NPA distinction

The current classifier is per loan and operational. It folds the current
contractual schedule and dated repayment/reversal allocations, finds the oldest
obligation with unpaid principal or interest whose due date is before today, and
calculates DPD from that due date. A partial payment does not reset DPD while that
oldest obligation remains unpaid. Grace affects operational escalation, not the
contractual due date or DPD. A bullet loan's age alone is not payment delinquency:
its actual schedule determines when money becomes due.

| Performance | Default condition |
| --- | --- |
| Standard | DPD below 1 |
| Watch | DPD from 1 through 89 |
| Substandard | DPD at least 90 |

The effective Workspace/license monitoring policy can change these thresholds.
Substandard raises DPD_SUBSTANDARD and critical review severity. It is not an
implemented statutory NPA decision. The compliance-profile field identifies a
policy; it does not load a regulatory rules engine. Current code does not implement
borrower-wide NPA contagion, NPA upgrade/cure rules, doubtful/loss aging,
provisioning or regulatory income-recognition rules.

For context, the [RBI's April 2025 commercial-bank circular](https://rbi.org.in/scripts/NotificationUser.aspx?Id=12822)
uses more-than-90-day overdue wording for term loans and includes broader
classification requirements. This illustrates why our configurable >=90-day
operational label must not be represented as regulatory compliance. Applicable
requirements need review for the intended lender type before adding an NPA module.

Collateral risk is independent: coverage exposure of INR 100,000 against eligible
collateral worth INR 90,000 produces a INR 10,000 full shortfall even when DPD is
zero. Conversely, a seriously overdue loan may still have ample collateral. LTV
limits can raise warnings before a full shortfall; unavailable valuation evidence
means unknown coverage, not zero value or automatic NPA classification.

## Change evidence age limits or monitoring thresholds

1. Open **Loan setup → Economic setup → Monitoring policy history**.
2. Choose **Amend** on the latest open-ended policy for the intended scope.
3. Review the prefilled settings and effective date. Set a date today or later and
   provide an amendment reason. Quote/appraisal age limits are inclusive calendar
   days: 7 allows seven-day-old evidence; zero requires same-day evidence.
4. Save. A new linked version records your identity and reason. Existing policy
   values remain in history. Another user saving first requires you to reload and
   review the latest version.
5. Refresh affected loans from Loan health, or let the configured worker process
   them. A future-dated amendment becomes applicable on that date.

Use the blank monitoring form for a new scope, and **Amend** for a scope
with an existing open-ended policy. A license override changes monitoring policy,
not staff visibility. Changing monitoring limits does not change agreed interest,
fees, origination requirements or settlement rules. Keep those decisions separate.

## Enable automatic refresh

The application provides a repeating command and an optional Compose service.
They are not enabled just by visiting Loan health. Use restricted runtime database
credentials; never run a worker under the owner-only migration settings.

For local development in PowerShell, replace `123` with the Workspace's numeric ID:

```powershell
.\.venv314\Scripts\python.exe manage.py check --database default --settings django_project.settings.dev
.\.venv314\Scripts\python.exe manage.py reassess_pawn_loans --workspace-id 123 --batch-size 50 --repeat-seconds 300 --settings django_project.settings.dev
```

The second command stays running; Ctrl+C stops it. For an existing Compose
installation, after applying migrations and building/selecting the application
image, set `ROKKAD_MONITOR_WORKSPACE_ID` and start the optional service:

```powershell
$env:ROKKAD_MONITOR_WORKSPACE_ID = '123'
docker compose --profile monitoring up -d monitoring
```

For production Compose use the corresponding `-f docker-compose.production.yml`
file and its existing runtime environment. The worker runs startup role/migration
checks. This guide is configuration, not a claim that production or the local
background service has been started. A process can serve multiple explicitly
selected Workspaces in turn. For example:

```powershell
.\.venv314\Scripts\python.exe manage.py reassess_pawn_loans --workspace-id 123 --workspace-id 456 --batch-size 50 --busy-seconds 1 --repeat-seconds 300 --settings django_project.settings.dev
```

The supplied order determines turns; duplicate IDs are ignored. Configure process
counts and Workspace lists explicitly; identity never comes from a user's
last-selected Workspace. The optional Compose profile still supplies one ID.

Each turn processes at most 50 candidate loans in this example. Each loan commits
separately, releasing its lock before the next loan. Unassessed loans go first,
then older attempts; each candidate is attempted at most once per turn. A failure
does not roll back loans already committed or prevent other Workspace turns.

After giving every configured Workspace a turn, the worker waits one second while
assessments are succeeding (`--busy-seconds`, configurable from 1 to 60). When no
assessment succeeds, it waits the idle/error interval (`--repeat-seconds`, five
minutes here). A failed loan cannot cause an immediate retry loop within its turn.
Archived/suspended Workspaces are refused, including if lifecycle changes during
a pass. Monitor logs (`selected`, `current`, `errors`) and the page's outstanding counts; this is
bounded polling, not a guarantee that all loans update immediately after a change.

Omit `--repeat-seconds` for a single pass or an OS scheduler. A one-shot run exits
with failure when assessments fail. Only one-shot mode permits `--as-of YYYY-MM-DD`;
a historical/future projection is outdated on today's portfolio. Repeated mode
uses the local date anew every time, opens/closes a separate transaction context
for each loan, and continues reporting failures until stopped. It sends no emails or WhatsApp messages.

See [the worker decision](../adr/2026-09-11-monitoring-worker-turns.md) and
[container operations](../implementation/container-and-ci.md).
