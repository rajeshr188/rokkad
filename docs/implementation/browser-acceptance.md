---
status: active
owner: project
updated: 2026-09-08
tags: [acceptance, browser, loans, party]
related: [mvp-operator-acceptance.md, ../STATUS.md]
---

# Browser acceptance

The opt-in `django_project.browser_acceptance.BrowserAcceptanceTests` runs
Chromium against Django's isolated test database and localhost static-file
server. It reuses the HTTP acceptance fixtures for an authenticated Owner,
Workspace, real trial, licence, series, and active lending product. Setup and
login are fixtures, not browser-tested onboarding flows.

Every new database connection, including the browser server's connections,
assumes a temporary role without superuser or RLS-bypass privileges. The role,
test rows, and temporary media are cleaned up. Development data is untouched.

## Run

```powershell
.\.venv314\Scripts\python.exe -m pip install -r requirements-browser.txt
.\.venv314\Scripts\python.exe -m playwright install chromium
.\.venv314\Scripts\python.exe manage.py test django_project.browser_acceptance.BrowserAcceptanceTests --settings django_project.settings.test --noinput --keepdb -v 1
```

Network access is needed for the application's existing CDN styles/scripts.
A sandbox run that blocks those assets cannot establish normal layout behavior.
The harness is deliberately outside automatic `test*.py` discovery. Browser
tooling is optional and separate from production dependencies.

Artifacts default to `%TEMP%\rokkad-browser-acceptance`; set
`ROKKAD_BROWSER_ARTIFACTS` to choose another output directory. Each run overwrites
matching screenshots, downloaded PDFs, and `report.json` in that directory.

## September 8 findings

Chromium 151.0.7922.34 completed the following at 1440x1000 and 390x844:

- Create a borrower through the rendered Party form.
- Show draft validation errors, search/select a borrower through Select2, and
  select the lending series and product.
- Add/remove a collateral row, attach a photograph, save a draft, approve,
  disburse, repay 1,000 against 10,000 principal, and complete full release.
- Check screenshots and document-width overflow on eight pages per viewport.
- Download ticket, repayment receipt, and release memo through visible links;
  download each again and compare exact bytes.

No JavaScript errors, failed asset requests, or horizontal document overflow
were recorded in the completed run. Mobile means a Chromium viewport, not a
physical phone or Safari certification.

Two reproduced blockers were fixed:

1. Borrower lookup used `/select2/` without Workspace identity. PawnDraftForm now
   supplies a named `workspace_party:party_autocomplete` URL. The existing Party
   view permission applies, middleware establishes the Workspace/RLS context,
   and django-select2 binds cached widget tokens to their issued URL. Restricted
   HTTP tests cover successful lookup, cross-Workspace token rejection, invalid
   tokens, and permission denial.
2. A new draft rendered `min_num=1` plus `extra=1`. The extra row's default metal
   made it participate in validation, blocking a one-item submission. The draft
   now starts with one row (`extra=0`); operators add more explicitly.

The focused regression gate passes 510/510 tests across Loans, Party, the MVP
HTTP journeys, route intent, and app authorization conformance.

## Camera and print limits

The browser harness simulates `NotAllowedError` and verifies that the camera
button opens the upload picker and accepts a JPEG. It does not certify physical
capture. A separate attempt with Chromium's fake camera and granted permission
returned `NotSupportedError` in this Windows environment.

Downloaded samples were parsed as A4 PDFs: ticket two pages, receipt one page,
release memo two pages. The ticket and release memo previews were visually
reviewed; text and table cells were readable. Physical printer margins,
pagination preferences, and signature placement still need operator acceptance.
The release memo continues its verification/signature content onto page two.

Physical camera permission/capture, actual mobile-device behavior, paper output,
and real collateral handoff remain pending. No notification was sent.

## Physical acceptance session preparation

The operator identified a Redmi Note 14 Pro. Windows lists a
`Canon G3010 series (Copy 1)` printer with driver status `Normal`; this does not
confirm that it is reachable, loaded with paper, or the intended test printer.
The operator explicitly deferred mobile checks and then printer tests. Browser,
reachable test URL, and printer/paper details can be confirmed when resuming.

The five-page `operator-print-samples.pdf` in the browser artifact directory
combines the desktop sample ticket (pages 1-2), receipt (page 3), and release memo
(pages 4-5). It contains synthetic acceptance data. Its companion
`operator-print-manifest.json` records the source document hashes. Nothing has
been submitted to a printer.

After the printer and A4 paper are confirmed, print at actual size (100%),
single-sided. Record whether all five pages print, edges and tables are unclipped,
Original/Duplicate labels are readable, and verification/signature content is
usable across the release memo's page break.

For the phone check, first establish a reachable isolated test Workspace and
record the browser and URL. On a test collateral form, allow camera permission,
capture an item, save it, and reopen its photograph. Then deny camera permission
and verify file upload remains usable. Confirm borrower search, add/remove
collateral, and portrait/landscape navigation. Physical capture and printed
output remain unverified until the operator reports their observations.
