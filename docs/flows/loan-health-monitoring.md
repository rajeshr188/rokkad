---
status: active
owner: loans
updated: 2026-10-12
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

The in-app **Loan monitoring guide** is linked from Loan health, Operations console
and the dashboard Financial health block for owners/admins. It is GET-only
reference content: opening it does not calculate or refresh loans, change policy
or send messages. Its route is `/w/<workspace-slug>/loans/setup/operations/risk/guide/`.
The new guide requires an application release before it appears on production.
Developers should read the [architecture reference](../architecture/post-origination-loan-monitoring.md).

## Choose current monitoring valuation

Open **Loans setup → Calculation, fees and monitoring → Monitoring policy history**.
Select **Amend** on the latest policy in the intended Workspace/licence scope.
The **Current monitoring valuation method** defaults to preserving each loan's
saved method. For paper/imported loans this need not prove the original lending
valuation. Choose current calculated metal value, latest approved appraisal,
or their lower value only after reviewing what collateral/evidence the business
can support. Save a reason and an effective date of today or later. Earlier
versions and original loan economics remain intact. A licence policy replaces the
complete Workspace policy; its preserving choice uses each loan's saved method.

Metal monitoring needs fresh prices and recorded weight/purity. Appraisal needs
fresh approved appraisal evidence. Lower-of needs both. Changing the choice does
not invent approval evidence or paper transactions. Refresh then calculates the
applicable current position and records the actual/original method in provenance.
Older contracts appear outdated until refreshed by the matching web/worker release.

Operational grace is taken from the frozen product or accepted opening agreement,
not the monitoring policy. The calculator returns an escalation-eligibility
indicator without moving DPD. Current risk flags/alerts do not consume it as a
general suppression gate; do not assume grace delays every alert.
Severity is derived from actual risk conditions; no separate severity-mapping input
is offered. Legacy policy grace/mapping values remain retained evidence.

## Read the portfolio

- **UNASSESSED:** no saved assessment exists. Use Refresh.
- **STALE:** the date, calculation contract or source evidence changed. Refresh
  before using the amounts. Yesterday's assessment is outdated even if nobody
  edited the loan.
- **ERROR:** an assessment failed. Open the loan, correct the reported setup or
  evidence problem, then refresh. Inconsistent financial evidence cannot support
  current money, DPD, LTV or a healthy classification; failed metrics are unavailable.
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

Summary totals use the usable current assessment subset, with affected counts and
provisional verification disclosed; they show **Unavailable** when no usable
monetary assessments exist. Whole-portfolio completeness requires all active
loans to have usable results and suitable transaction coverage. Unknown coverage has a separate
count among current assessments. Metric filters use current results only. Internal
alerts retain their assessment dates; review live details before acting. Nothing
is sent to a borrower merely by opening or refreshing this page.

An LTV breach becoming critical keeps its alert open and raises severity. Missing
valuation or a failed assessment does not prove recovery, so the existing alert
remains open while its condition is unknown. A successful assessment showing the
condition has cleared resolves it with a linked confirming event. A later return
of the same risk is a new incident, even on the same day with identical values.
This does not create an automatic borrower message or change the loan's debt.

MR-04 adds database protection for these relationships: a transition cannot be
edited/deleted, and an alert's original loan/source stays fixed. Assessment values,
alert severity and confirmed resolution remain writable. A manually created
risk-linked borrower notice retains that alert's exact original source event.
See [the database protection decision](../adr/2026-10-11-risk-evidence-database-protection.md)
and [local validation/release prerequisites](../implementation/risk-evidence-guards-mr04.md).

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

Live refresh always saves today's local position. A historical or future date is
rejected before changing the saved assessment, events or staff alerts. Read-only
dated calculations remain available to code/reporting callers; they restate the
position from available evidence and do not certify a captured past assessment.
The routine page uses the server's date when Refresh is submitted.

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
oldest obligation remains unpaid. Grace supplies an eligibility indicator, not a
shifted due date/DPD or integrated alert suppression. A bullet loan's age alone is not payment delinquency:
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

MR-06 activated one bounded restricted worker for JCL, JSK and Lakshmi on
12 October 2026 IST. It runs continuously alongside the web app; the six existing
mail/backup/storage timers are separate. Initial assessment catch-up does not
supply missing valuation evidence or certify paper books. See the actual
[release evidence and coverage limits](../implementation/monitoring-release-mr06.md).

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
last-selected Workspace. Production Compose now accepts an explicit list:

```powershell
$env:ROKKAD_MONITOR_WORKSPACE_IDS = '123 456'
docker compose -f docker-compose.production.yml --profile monitoring up -d monitoring
```

Its startup helper refuses empty/invalid scope and checks the restricted runtime
role and pending migrations before starting. The previous singular setting is
compatible. Initial production defaults are ten candidates per Workspace, a
five-second busy pause and 300-second idle/error pause, capped at 0.35 CPU and
512 MiB for one process. Set explicit environment overrides only after measuring
backlog and foreground response time. See [MR-06](../implementation/monitoring-release-mr06.md).

Each turn processes at most 50 candidate loans in this example. Each loan commits
separately, releasing its lock before the next loan. Unassessed loans go first,
then older attempts; each candidate is attempted at most once per turn. A failure
does not roll back loans already committed or prevent other Workspace turns.

After giving every configured Workspace a turn, the worker waits one second while
assessments are succeeding (`--busy-seconds`, configurable from 1 to 60). When no
assessment succeeds, it waits the idle/error interval (`--repeat-seconds`, five
minutes here). A failed loan cannot cause an immediate retry loop within its turn.
Archived/suspended Workspaces are refused, including if lifecycle changes during
a pass. A commercial access denial is reported for that Workspace and does not
stop the other explicitly configured Workspace turns. Monitor logs (`selected`,
`current`, `errors`, `as_of`, `elapsed_seconds`) and the page's outstanding counts; this is
bounded polling, not a guarantee that all loans update immediately after a change.

Omit `--repeat-seconds` for a single pass or an OS scheduler. A one-shot run exits
with failure when assessments or Workspace turns fail, after attempting the other
configured turns. Only one-shot mode permits `--as-of YYYY-MM-DD`, and that date
must be today; another date is rejected before any turn. Repeated mode
uses the local date anew every time, opens/closes a separate transaction context
for each loan, and continues reporting failures until stopped. Ctrl+C and SIGTERM
stop the worker cleanly; an interrupted loan transaction unwinds while prior
completed loans remain committed. It sends no emails or WhatsApp messages.

See [the live boundary decision](../adr/2026-10-11-live-risk-assessment-boundary.md),
[the worker decision](../adr/2026-09-11-monitoring-worker-turns.md) and
[container operations](../implementation/container-and-ci.md).
