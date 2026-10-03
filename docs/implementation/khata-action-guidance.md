---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, workflows, drafts, guidance, verification]
related: [khata-operational-reports.md, ../flows/khata-account-workflow.md, ../plans/future-work.md]
---

# Khata action prerequisites and draft experience

The later [document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime. This guidance checkpoint retains its dated identity and evidence.

Phase six adds advisory source status and next steps to Overview/Actions. Latest
saved proposal, current terms source and recorded approval remain distinct; neither
saving nor approval activates terms. First payout opens the agreement. Dated stale
proposals guide today's review; exact source links retain audit context.

Buttons filter known prerequisites: held/photo/return existence, cancellation only
after unopened holdings are returned, received exchange alternatives, pending
current proposal, usable change approval, actual due interest and completed unsaved
periods. Activation guidance also respects actual cashier/approver/release authority.
This is presentation, never a substitute for service locking, signed review and
confirmation. Lending prices, policy, photos, actual cash/custody and state are still
revalidated by the unchanged commands.

Approval selection is bounded to the last operation, latest proposal, today's
business date and no activation use. The real activation-review comparison excludes
changed account/lending/return evidence without posting or locking a GET. Confirmation
reconstructs signed instructions with the original account-scoped approval choices,
preserving successful replay/idempotency; the command still refuses changed evidence.

Actions now intentionally loads the compact canonical money schedule to explain
actual due/next anniversary and optional finalization. History, Collateral and
Documents retain source-only reads; there is no persistent balance cache.
Interest receipt automatically finalizes elapsed periods atomically. Separate
finalization receives no cash and is optional; it appears only for unsaved completed
periods. Annual unbilled interest remains on its anniversary schedule.

## Draft

Reuse Party's stateless Workspace-bound active borrower autocomplete and the existing
borrower-outstanding panel, including actual Khata debt rather than limits. A native
GET search lists at most 25 active matches by name/code/phone for no-JavaScript use;
search before filling terms because it reloads the form. Foreign/inactive identities
cannot be selected. Outstanding remains advice, not a credit decision or settlement.

A private GET illustration reuses KHATA-1 and the TermsForm's decimal/rate/frequency
validation. It assumes first withdrawal today and unchanged terms, shows one full
month, the first scheduled monthly/annual bill and the original anniversary due.
Annual payment keeps the monthly rate unit. Short-month/leap clamps, zero rates and
paise rounding come from the calculator. Changed inputs cancel/discard stale requests;
invalid/unavailable estimates never show zero as a fallback. Draft review displays
the same server illustration without JavaScript and before any account is created.

## Opening acknowledgement design (not implemented)

Recommend a staff-recorded borrower agreement/reference on opening approval, linked
to the exact proposal and disclosed at first payout. It should identify actual paper
or other retained agreement evidence; a checkbox or staff login must not pretend to
be a borrower signature. Changes require fresh approval. The existing change-approval
consent reference remains unchanged. Before implementing opening evidence, specify
its required/optional boundary, immutable schema/guard and review-hash treatment,
PDF/recovery/portability compatibility and historical acceptance. This phase adds
no mandatory acknowledgement, e-signature or new financial permission.

## Verification and runtime

The successful frozen image passes **469 Linux regressions in 286.994 seconds**,
including the existing archive checks and 11 new guidance tests. Coverage includes
stale/used approvals, changed lending evidence, cashier/approver boundaries,
idempotent confirmation choices, real dues, no-source-write illustrations,
monthly/annual rate units, rounding and native Workspace-bound borrower search.
Schema/no-drift, dependency, restricted-runtime/static and owner-startup-refusal
checks pass. No schema or financial service is changed.

Actual read-only browser acceptance passes for source status, prerequisite filtering,
borrower autocomplete/outstanding, monthly/annual estimates, private headers,
viewer refusals and native search. Existing tabs, servicing, custody pagination/QR,
collections/events, exception guidance and cash/custody reports also pass. Four
new desktop/mobile screenshots are inspected, with no document overflow or page
JavaScript errors. QA uses exact configured Bootstrap 5.3.8 bytes/SRI; app asset
configuration is unchanged. Historic cash fixtures use their actual 2 October date;
today's empty cash range is not treated as missing records. No financial/custody
confirmation is submitted.

An initial focused-test error came from a stale in-memory fixture and was corrected.
The first frozen attempt caught the old layout expectation and a duplicate suggested
action link. Actions now names the suggestion without duplicating its grouped button;
Overview retains the shortcut. That rejected image was never activated. Browser
harness tab URLs were corrected to the existing `tab` parameter; no application
edit follows the successful freeze.

The local image is composed from prior verified `khata-local-20261002-2fc1557b6beb`
plus 15 explicit Khata application paths. Models, financial services, migrations
and all unrelated application files retain their base bytes. Separately evolving
ordinary Loans work stays in the checkout and is not activated in this pilot.
The composed URLs preserve the base routes plus only the draft-estimate route.
All **1,424 application/settings files** match the frozen manifest and actual image.

At this guidance checkpoint, local candidate: `khata-local-20261003-ac52235bea54`; image
`sha256:06f7970074913db752104ea62c18cd2e0aa461948744a618782d591b0048af5e`.
Source digest: `ac52235bea546ff8da9d6720947690035c0349965526acb5098c4fc0c839768c`;
archive digest: `ee1b95332cda4714a50b86466c31c76df1274580edd884b8059fa94aef0d4d2d`.
Private evidence: `.tmp/khata-guidance-candidate-20261003-v2/`.
The active web is non-root with read-only root and separate static volume
`khata-guidance-20261003-v2-static`. Fictional database/media persist; pre-update
backup hashes and stopped rollback `khata-img-20261002-web-pre-guidance-20261003`
are retained. This is an uncommitted local snapshot, not remote CI or a production
release. Hosted/operator recovery, physical camera/printer/QR acceptance and broader
correction/reminder contracts remain separate. Next: authorized series pause/retire
controls, preserving servicing and numbering history.
