---
status: verified-local
owner: loans
updated: 2026-10-03
tags: [khata, paper-entry, candidate, recovery]
related: [../flows/khata-and-paper-first-release.md, ../flows/khata-test-pilot-acceptance.md, ../flows/paper-first-operator-and-release.md]
---

# Combined Khata and paper-first local candidate

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
