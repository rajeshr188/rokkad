---
status: verified-local
owner: loans
updated: 2026-10-03
tags: [khata, paper-entry, candidate, recovery]
related: [../flows/khata-and-paper-first-release.md, ../flows/khata-test-pilot-acceptance.md, ../flows/paper-first-operator-and-release.md]
---

# Combined Khata and paper-first local candidate

## UR-23 update: compact New loan entry

The current fictional candidate on [localhost 8078](http://127.0.0.1:8078) is
`rokkad:entry-refined-20261003-a80e473e`, through existing Loans migration
`0057_default_entry_purpose`. Scoped baseline `22db74f8` still excludes unrelated
billing/platform/storage changes. All **1,529** runtime source files match;
archive SHA256 is
`a80e473e73225321abb017769366d1ba19d38336ea8495e88e0daa592ea626e4`.
The running web image also matches the verified manifest. Restricted-role checks
confirm `joint_pilot_runtime` without superuser/RLS bypass. No migration was added.

Ordinary Series now applies the purpose default, with compact Entry/Change instead
of duplicate selectors or prominent navigation. Final **142 affected tests pass
in 78.846s**. Actual desktop/mobile/no-JavaScript round trips retain customer,
original date, item principal/quantity, paper book/number and native appraisal/rate
override. JavaScript retains the actual selected photograph input without uploading
it during a change. No-JavaScript entry retains facts and explicitly requests file
reselection after switching. Native add/remove reinitializes; removed rows remain
hidden. Changing purpose invalidates a reviewed paper record; normal direct
price/date preflight still blocks an ineligible earlier-date decision. Existing
saved PDF URLs serve their exact hashed bytes. Tested forms have no horizontal
overflow or page errors. A controlled delayed-response-body check also confirms
new typing is retained and the stale response is retried without a submission.

Desktop browser admission P-0056 independently verifies original date 25 September,
12-month tenure, one item with quantity 2 and principal 6,000 at 2%, advance interest
120, document charge 10 and proceeds 5,870. No digital approval or actual cash paid
was invented. Earlier fictional refinement trials P-0050 and P-0053 are retained;
duplicate-number and duplicate-source-reference guards correctly rejected attempts
to reuse their facts during harness retries. Mobile P-0057 and no-JavaScript P-0058
were reviewed only. Existing trial 1234 retains its three-month tenure.

Private evidence under `.tmp/loan-entry-refinement-20261003` includes the manifest,
test/browser reports, screenshots, final runtime/financial check and identical
before/after existing loan/file fingerprints during update. Previous containers and
the verified pre-UR19 database/media backups remain retained; this UI-only slice
does not claim a new backup or native export. Candidate 8077 and production are
unchanged. Real paper/staff/hardware and hosted release checks remain pending.

## UR-19-22 update: shared multi-item entry

This previous checkpoint used
`rokkad:shared-entry-20261003-d91d4ea3` through Loans
`0057_default_entry_purpose`. Its scoped baseline remains `22db74f8`; unrelated
billing/platform/storage work is excluded. All **1,525** runtime source files match.
Source archive SHA256:
`d91d4ea37767b9026aa90a07e1e219ae74a682ffb440faeec522c711272601ec`.
Restricted read-only runtime startup, owner startup refusal, owner-only migration,
model consistency and dependencies pass. The fictional P series now defaults to
paper entry through an appended current economic revision; existing rates, fees,
loan contracts, events, custody/document rows and file bytes were unchanged.

502 regressions (445.006s), 105 overlapping final receipt/draft checks (61.683s)
and actual browser checks pass. Desktop/mobile admit multi-item paper loans;
desktop records a staff-specified receipt and mobile records full closure across
both items. No-JavaScript add/review preserves submitted facts. Explicit direct
routing and shared add/remove controls work. Existing saved PDFs have exact hashes,
with no horizontal overflow or page errors in the tested forms. A browser-discovered
confirmation-checkbox invalidation bug is fixed in the final image.

The independently verified P-0043 agreement has 6,000 gold at 2% and 4,000 silver
at 4%; advance interest 280, document charge 10, proceeds 9,710 and tenure 12 months.
A 2,000 dated receipt applies 1,500/500 principal as entered by staff, leaving
4,500/3,500; following-anniversary interest is 230. Current monitoring shows known
8,000 exposure without claiming complete-book verification. P-0044 is financially
closed at 10,000 with both items PAPER_CLOSED and customer handover unconfirmed.
Earlier P-0040/P-0041 browser cases also remain as fictional acceptance records.
The existing trial loan 1234 keeps its original three-month tenure.

The pre-UR19 physical database backup passes `pg_verifybackup`; database/media
archives and previous images/containers remain retained. Their private hashes,
full source manifest, browser screenshots and financial/native export evidence are
under `.tmp/multi-item-paper-20261003`. The final schema-matched Pawn archive is
`shared-entry-pawn-native.zip` (SHA256
`c05ada88e711c766ff75cf2d6dc2bcdb655f2afabb984dcd0cbe764914f9cd23`). Do not use the
previous-schema native archive to bypass restoration compatibility checks.
Candidate 8077 and production remain unchanged. Real paper/staff/hardware acceptance
and hosted release checks remain pending. The optional completed linked paper-renewal
shortcut retains its one-group boundary; independent multi-item entry/closure and
ordinary Renew performed now are supported.

## UR-15–18 update: routine paper entry

This is the earlier checkpoint; the current image and verification are above.

The authorized simplification is complete locally. The same fictional workspace
on [localhost 8078](http://127.0.0.1:8078/w/khata-2777349a/loans/internal/create/?entry=paper)
now runs `rokkad:paper-simple-20261003-c5462662`, a scoped worktree snapshot over
committed baseline `22db74f8`. Source archive SHA-256 is
`c5462662f9fec989e71343a29604d6663b46cf99dac0579cabffa9fbc222fb5f`;
all 1,519 runtime files match. Unrelated pending billing/platform changes were not
included. Loans migration 0056 applies with no model drift; owner startup refusal,
restricted production startup and dependency checks pass. Web remains read-only,
on its internal network and restricted runtime role; 8077 and production are unchanged.

The fictional P series supplies 12-month tenure, gold 2%/silver 4% monthly interest,
one month in advance, deducted INR 10 document charge and current monitoring.
New entries prefer its eligible Flexible Partial Payment version. Existing loans
retain their original product, rate and tenure, including trial loan `1234` at
three months. Setup changes do not reprice them.

422 final cases pass in 369.684 seconds; 156 affected cases also pass, overlapping.
Actual desktop/mobile/no-JavaScript standing terms, calculated proceeds and signed
review pass. Automatic refresh preserves facts being typed in other fields. Existing
Khata/paper navigation, joint borrower totals, exact issued-PDF hashes and viewer
restrictions pass. The existing trial loan 1234 makes the pre-new-example joint
borrower baseline six active loans, principal INR 2,40,400 and displayed outstanding
INR 4,40,400; the older five-loan baseline below is its original checkpoint.

| New fictional example | Verified result |
| --- | --- |
| [P-0020](http://127.0.0.1:8078/w/khata-2777349a/loans/internal/17/) | Principal 12,000; 12 months; advance interest 240; document charge 10; proceeds 11,750. Browser-posted 27 September receipt 2,000 reduces principal to 10,000; first month was already paid in advance. Current calculated exposure 10,000 is displayed provisionally without a fabricated whole-book review. |
| [P-0021](http://127.0.0.1:8078/w/khata-2777349a/loans/internal/19/) | Same standing agreement; browser-posted closing settlement 12,000; financially Closed, system-assigned closing number, handover unspecified. No invented cash payout, original approval or complete-book review. |

Before the update, `pg_basebackup` plus `pg_verifybackup` retained a physical
database backup and media copy. The old web containers and images remain stopped
and available. A new ordinary-Loans native ZIP includes schema 0056 and the new
records. Earlier 0055 native archives require their matching old image/schema;
restore that checkpoint before upgrading. Private evidence and checksums are in
`.tmp/paper-simplification-20261003/`. Real-record staff acceptance and production
rollout remain separate release steps.

## Original combined acceptance checkpoint

The owner authorized the next combined acceptance step after local commit
`22db74f86db42ef175547fd38a4b96206dde4324`. No additional feature implementation
was started. Remaining Khata enhancements stay deferred in
[Future work](../plans/future-work.md#improvement-delivery-sequence).

## Exact source and isolated runtime

Image: `rokkad:joint-loans-20261003-22db74f8`.
Image ID: `sha256:86fe1625f1138bae237b56cc5fa8182b990fdc759d4f37077e1be73b8986ba99`.
The Git archive contains 3,066 committed files; all 1,515 application/settings/
template/static files selected for the actual runtime image match their recorded
SHA-256 values. Uncommitted billing, console and storage application changes are
excluded. Post-build documentation updates do not change this image's source.

The new persistent database/media/static volumes use the `joint-loans-20261003`
resource prefix and an internal Docker network. PostgreSQL has no host port.
Web runs as `app` with a read-only root and restricted `joint_pilot_runtime` role,
without owner credentials. A credential-free relay exposes only
`http://127.0.0.1:8078`. Local HTTP uses `container_dev`; the production settings
startup checks pass separately with the restricted role. Owner startup correctly
fails with `tenancy.E020`. The complete merged migration graph applies through
Loans `0055_dated_custody_business_day`; migration-current, model-drift and
dependency checks pass. The existing Khata-only pilot on 8077 remains unchanged.

## Review the fictional workspace

Workspace: `khata-2777349a`, display name **Combined loans fictional acceptance**.
Open the [combined Khata register](http://127.0.0.1:8078/w/khata-2777349a/loans/khata/).
Private owner/viewer credentials are retained in
`.tmp/joint-loan-pilot-20261003-v1/pilot-login.txt`; do not publish that file.

| Example | Retained outcome |
| --- | --- |
| KH00001 | Same-metal warned exchange of one item for two; actual old-item handover; formal reduction from INR 1 crore to 60,000 with 40,000 principal repaid and sufficient remaining cover; reduction handover; settlement and final handover; Closed |
| KH00002 | Monthly agreement, INR 1 crore limit, 1% per month, actual principal 1 lakh, first due 3 November 2026 |
| KH00003 | Annual agreement with the same monthly rate unit and actual principal; first due 3 October 2027 |
| KH00004 | Unopened draft; consumes its own KH number, owes no principal/interest |
| P-0010 | Original paper loan dated 25 September, principal 10,000 at 2% monthly; actual total receipt 2,000 on 27 September allocates 200 interest and 1,800 principal; principal now 8,200 |
| P-0011 | Recorded closing settlement 10,200; financially Closed with `PAPER_CLOSED` collateral and unknown physical handover |
| P-0012 | Independent paper loan principal 12,000, advance interest 240 and document charge 10; proceeds 11,750; actual physical cash remains unconfirmed |
| P-0013 → P-0014 | Known recorded renewal carries 8,200 after a 2,000 receipt/settlement, successor rate 1.5%; no fabricated successor disbursal cash |

All examples use canonical commands under runtime RLS. Paper previews roll back
before admission. A reused fictional source reference was correctly refused;
remaining examples received distinct book/loan references without editing posted
evidence. Fixture setup also reuses completed examples when resumed.

Desktop, 390px mobile and no-JavaScript browser checks pass on the register,
monthly/annual/closed accounts, collections, paper loan/closure and backlog pages.
There is no page-level horizontal overflow or application JavaScript error.
Mobile section navigation and its native GET fallback work. Visual inspection
covered the Khata register and ordinary paper-loan mobile layout.

The [borrower's Loans tab](http://127.0.0.1:8078/w/khata-2777349a/parties/1/?tab=loans)
contains both products. The new-loan borrower summary shows five active loans,
principal **228,400** and displayed outstanding **428,400**, including accrued
Khata interest **200,000** and excluding borrowing limits/unposted ordinary-loan
interest. It explicitly remains a summary rather than a settlement quote.

Two statements and two combined 100 × 60 mm labels are saved through normal
issuance. Authorized reprints match their exact original PDF hashes and use
private no-store responses. Viewer export/posting, foreign Workspace access and
missing-CSRF posting are refused; no-context Loans queries return no rows.

## Recovery evidence and operational limitation

Private evidence is under `.tmp/joint-loan-pilot-20261003-v1/`: frozen manifest,
provision/fixture/browser reports, original native archives, full database/media
backups, independent checksum record, recovery reports and browser screenshots.
These contain fictional data and private credentials/configuration. They are
local rehearsal artifacts, not proof of off-device production backup retrieval.

The initial logical `pg_dump`/`pg_restore` round trip preserves every public table,
sequence and media hash and passes restricted startup. Ordinary native restore
correctly refuses its destination because PostgreSQL deparses two CHECK cast
expressions differently: `loans_funding_state_valid` and
`loans_policy_basis_valid`. Model schema, other guard definitions and data match.
The fingerprint check is not relaxed or bypassed. Do not assume a logical full
restore supplies an exact-guard destination for an earlier native archive.

Owner migration settings default to a developer media directory. Offline native
recovery must explicitly select the actual restored private-media destination.
The rehearsal uses `/var/www/rokkad/media` through a scoped settings override;
neither web settings nor source financial rules are changed.

Physical recovery passes on a separate fictional PostgreSQL server. Source and
copied backups both pass `pg_verifybackup`; recovered public tables, sequences,
roles and media match: **202 public tables, 199 sequences and 9 media files**.
Both native formats then pass real rolled-back previews
and committed restores into separate offline empty destinations with matching
original identities/guards. All public table and media fingerprints remain exact;
native PK sequences stay monotonic. Restricted production startup passes after
each native restore. The operating candidate's rows, sequences and media are
unchanged by the recovery rehearsal. No off-device retrieval is claimed.
The separate recovery server is stopped after verification; its persistent volume,
database copies and backup evidence are retained. Both operating pilots keep
running. Final checks pass 741 local documentation links and confirm both saved
label PDF page boxes are 100 × 60 mm.

## Remaining acceptance and release steps

1. Review these examples with named staff using the two operator guides. Technical
   checks do not pre-fill staff acceptance. A real Lakshmi book comparison is
   required before relying on entered real balances, not to build/test this
   candidate; the owner need not send real customer facts in chat.
2. Complete physical 100 × 60 mm print, camera and authenticated phone QR checks.
   A phone's localhost points to that phone, so laptop-only 8078 is not a hosted
   mobile pilot. Hosted staff access needs its own selected environment.
3. Select and approve rollout after acceptance. Retain actual target database/
   media backups, old/new image IDs and checksums; rehearse that target's recovery
   method, including the exact-guard limitation above. Apply owner-only migrations,
   then use restricted roles for web/workers and run the joint release checks.

There is no production change, push, automatic paper admission, real Khata
activation or completed staff/hardware acceptance in this checkpoint. Both
workflows can be adopted separately even when their code ships together.
