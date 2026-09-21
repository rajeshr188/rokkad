---
status: active
owner: project
updated: 2026-09-21
tags: [migration, rehearsal, access, loans]
---

# Review the imported data in the local rehearsal

Open `outputs/linode-rehearsal-access-20260921/access.html` for the dedicated
username/password and direct links to each branch's outstanding loans, customers
and closed history. This private file is not committed or served by Django.

The login page is `http://127.0.0.1:8081/accounts/login/?next=/app/workspaces/`.
Sign in as `migration-rehearsal-owner` using the password in the access file.
Choose Rehearsal JCL, Rehearsal JSK or Rehearsal Lakshmi Pawn Broker. The yellow
**Local migration rehearsal** banner must be visible. Your usual account login and
the normal application's `jcl-13` database are separate.

## Review workflow

1. Open a familiar customer and outstanding loan. Check number, principal, original
   date, linked customer and collateral.
2. Open **How interest is calculated** on the loan page. Check months, interest due
   and the next monthly increase against the agreed legacy calculation.
3. Open **Closed history** from the access page for source-reported released loans.
   The 190 owner-reported closures have unknown release dates. JSK WH01223 is a
   cancelled source entry, so it does not appear as an operational loan.

Outstanding loan counts are JCL 2,355, JSK 1,483 and Lakshmi 2,435. Closed history
contains 39,133 records. Imported customer and address records are present. This
database contains the September 21 discovery snapshot, not later Linode changes.
Original photographs are not present in the database dump.

Edits here affect only the rehearsal database. Full settlement with interest catch-up
and coupled reversal is supported after the September 21 opening checkpoint;
ordinary partial repayments remain guarded. Current lending licences/products still
need setup acceptance before new lending. Testing a workflow here does not authorize
or complete production cutover. Local trial access lasts through October 5, 2026.

## Restart the local server

From the repository root in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_rehearsal_web.ps1 -DatabaseName rokkad_baseline_rehearsal_linode_20260921
```

Leave the terminal open and use the same login URL. Port defaults to 8081; an
explicit `-Port` selects another loopback port. Avoid starting another copy while
one already listens there. This is a local development server, not a production
deployment. The initially launched process ID and logs are in the private access
folder; stopping that process stops only this server, not PostgreSQL or the data.

`django_project.settings.baseline_rehearsal_web` inherits the existing explicit
rehearsal database-name guard and restricted runtime role. It has separate cookie
names, process-local cache, in-memory email, and file storage under
`outputs/<rehearsal-database>/media`. It does not run background delivery workers.
The inherited debug-toolbar middleware is omitted from this profile; its known
W001 configuration warning is expected. Authentication, CSRF, owner Membership,
Workspace lifecycle, subscription policy and forced RLS remain active.

## Verification completed

Three settings tests passed, including rejection of normal/missing database names
and proof that importing rehearsal settings leaves normal dev settings unchanged.
Actual loopback HTTP tests used password login and CSRF, rather than a forced test
session. The selector and 12 scoped pages loaded: loans, a sample loan with interest
explanation, customers and closed history for each branch. Requests for another
branch's loan ID returned 404, and anonymous loan requests required login. Static
CSS loaded and the login/banner were visually checked in the browser.

The owner account has no superuser/staff override. Trial creation used the billing
service with audit events; no provider purchase or outgoing message was made.
Before/after hashes match for Party, contacts, addresses, loans, events, collateral,
opening origins, closed evidence, schedules, obligations and numbering sequences.
Private verification and setup evidence are in the access folder; original sealed
import reports remain unchanged.
