---
status: active
owner: loans
updated: 2026-09-11
tags: [loans, monitoring, operations]
---

# Review loan health and change monitoring limits

Open **Loan setup → Operations console → Loan health**. This remains an
administration screen requiring workspace settings permission. Every active loan
appears, including loans that have never been assessed. Loan detail remains the
place for live calculations and collateral appraisal history.

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
background service has been started. Use one explicitly configured job per
Workspace; do not infer identity from a user's last-selected Workspace.

Each pass processes at most 50 loans in this example and waits five minutes after
completion. Unassessed loans go first, then older attempts. Errors are reported and
retried on later passes without blocking older pending work. A large backlog needs
multiple passes. Archived/suspended Workspaces are refused on each pass. Monitor
logs (`selected`, `current`, `errors`) and the page's outstanding counts; this is
bounded polling, not a guarantee that all loans update immediately after a change.

Omit `--repeat-seconds` for a single pass or an OS scheduler. A one-shot run exits
with failure when assessments fail. Only one-shot mode permits `--as-of YYYY-MM-DD`;
a historical/future projection is outdated on today's portfolio. Repeated mode
uses the local date anew every time, opens/closes its own transaction context, and
continues reporting failures until stopped. It sends no emails or WhatsApp messages.

See [the architecture decision](../adr/2026-09-11-complete-loan-monitoring.md) and
[container operations](../implementation/container-and-ci.md).
