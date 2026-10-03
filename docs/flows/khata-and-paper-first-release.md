---
status: verified-local
owner: loans
updated: 2026-10-03
tags: [khata, paper-entry, release, acceptance]
related: [khata-test-pilot-acceptance.md, paper-first-operator-and-release.md, ../plans/future-work.md, ../plans/unified-loan-recording.md]
---

# Release Khata and paper-first loan recording together

The owner requested one repository checkpoint of both implemented loan workstreams
and deferred remaining Khata enhancements on 3 October. A Git commit preserves the
code and decisions; it does not deploy them or certify real borrower books.

Khata keeps its own series, accounts, sources and agreed-limit interest calculator.
Paper-first recording uses ordinary Loans for independently numbered paper
agreements and subsequent receipts, closure, renewal and supported corrections.
Existing flexible loans keep their own product behavior. Do not convert existing
loans into Khata or automatically admit/certify historical archives.

The scoped checkpoint includes Loans, shared Party/Notify/portability integration,
loan-facing templates/scripts, evidence-retention and preceding loan migration
dependencies, including the existing storage-inventory schema/models, private-media
reference registry and checks required by those migrations/readiness. Separate billing, storage screens/
cleanup and platform-console application changes
remain outside it. Release from the committed tree rather than the dirty checkout.
The current Khata-only local pilot is an earlier composed image; do not assume it
contains paper-first recording or that its earlier native archives match this tree.

## Local and staff acceptance

The [combined local candidate](../implementation/joint-loan-candidate-20261003.md)
from `22db74f8` is verified at
http://127.0.0.1:8078/w/khata-2777349a/loans/khata/. Its migrations, fictional
canonical examples, desktop/mobile/no-JS browser checks, shared summaries,
immutable PDFs and full/Khata/ordinary recovery pass locally. Private credentials
are in `.tmp/joint-loan-pilot-20261003-v1/pilot-login.txt`. Named operator and
physical/hosted acceptance below remain pending.

1. Build a fresh isolated candidate from the exact commit, with PostgreSQL and a
   separate fictional database/media volume. Exercise the complete migration graph;
   both `0041` and both `0042` branches are intentional. Merges `0046` and `0050`
   join them; the final Loans leaf is `0055_dated_custody_business_day`. Do not
   rename/fake migrations or copy the Khata-only database's history into another
   target. Several preceding loan/portability migrations depend on
   `orgs.0010_storage_inventory`; retain that prerequisite unchanged. Use owner
   settings for migration and restricted roles for web/workers.
2. Test Khata in a new test Workspace with a separate independent series and
   fictional data. Follow the [Khata acceptance record](khata-test-pilot-acceptance.md):
   opening/draws, monthly and annual interest, revisions, exchange WARN/BLOCK,
   returns and settlement. Record named staff results. Retain 100 x 60 mm label,
   real camera and authenticated physical QR checks as manual acceptance.
3. Reconcile representative real Lakshmi paper examples in an isolated acceptance
   environment, using the [paper-first guide](paper-first-operator-and-release.md).
   Record original date/number/terms and actual total receipts, independent loans,
   a known renewal, closing deductions and unknown/later-confirmed handover.
   Verify expected cash, principal, interest, custody and transaction completeness
   against the actual book. Additional unsupported arrangements need explicit facts.
   Actual customer facts need not be sent in chat or supplied for the fictional
   build/test candidate; reconcile a book locally before relying on real entries.
4. Check existing JCL/JSK ordinary flexible origination, repayment, renewal and
   ticket/label printing against the same candidate. Keep original issued PDFs and
   compare balances; acceptance is about behavior, not automatic data conversion.

## Release and recovery

Select the rollout environment after acceptance. Retain full database/private-media
backups, exact old/new image identities and independent checksums; rehearse recovery
in an isolated destination. Both native formats require matching schema/guards and
external prerequisites. An archive from an earlier image may require that matching
image followed by forward migration; never relax a mismatch check. Full recovery
also preserves Party, Rates, actors, control-plane and original media prerequisites.

The combined rehearsal found that logical PostgreSQL restore rewrites two CHECK
cast expressions and ordinary native recovery correctly refuses their changed
guard fingerprint. Full logical row/sequence/media recovery passes, but it is not
an exact-guard destination for that saved ordinary native archive. Physical backup
verification and both native restores pass on a separate fictional server with
original definitions. Retain this distinction when choosing the rollout backup
method; never bypass the fingerprint check. Owner-only native recovery must also
explicitly select the actual private-media destination, rather than migration
settings' developer media default. See the candidate record for tested details.

Run the complete reviewed migration graph during a quiet window:

```powershell
python manage.py migrate --settings django_project.settings.migration
```

Collect static assets for the committed image, then start web and workers using the
restricted runtime role. Verify migration readiness, tenant isolation, login/roles,
shared borrower/dashboard summaries, print endpoints, ordinary Loans and Khata
servicing. No notifications are sent just because the feature code is present.

Start real paper recording only after book reconciliation, and real Khata only after
its named operator/policy and release acceptance. These can be adopted separately
even when their code ships together. Existing data is preserved; no bulk migration,
new series, policy activation or archive admission follows automatically from deploy.

After new source events exist, use a compatible forward fix or a reviewed recovery
and reconciliation procedure. Do not roll evidence migrations backward or discard
new financial/custody events. Remaining Khata development stays in
[Future work](../plans/future-work.md#improvement-delivery-sequence).

## Commit verification

The previous separate checkpoints passed 498 Khata and 745 paper-first regressions,
with browser/PDF evidence in their implementation records. Commit validation combines a broad run and a complete affected-module rerun.
**1,081 broad cases pass** in the initial 1,103-test run (632.856 seconds). Its 22 errors all came from an omitted private-media reference dependency, now included. **486 affected/integration tests pass in 295.000 seconds** across 33 modules on the corrected staged tree. Counts overlap. The corrected tree retains 2,263 frozen, checksum-verified source
files in an isolated directory. The rerun covers every failed Khata module, the
pledge-book media test and shared paper-first/tenant integration; unchanged passing
broad modules are not repeated. The complete migration graph has one Loans leaf,
`0055_dated_custody_business_day`; model drift and tenant/forced-RLS registry checks
pass. Fresh test databases are destroyed after each run. Source extraction needed
QA-only packaging fixes and existing storage-schema/media-reference prerequisites;
no financial or servicing behavior changes were needed for this joint verification.
Separate browser/PDF evidence remains as recorded. Commit verification itself did
not repeat browser or physical-device trials; the subsequent combined candidate
adds the actual browser/recovery evidence linked above. Physical-device acceptance,
production and remote CI remain untouched.
