---
status: active
owner: project
updated: 2026-09-25
tags: [rehearsal, acceptance, recovery, cutover]
---

# September 24 operational acceptance

This is the historical September 24 acceptance record for
`rokkad:rc-20260924-fd011920`, which served the practice database at that time.
On September 25 the owner separately authorized retained production operations
at the temporary hostname. Authentication/proxy setup, the final import, lending
setup and approved staff assignments were subsequently completed. See
[current Status](../STATUS.md) and the [cutover record](linode-production-cutover.md)
for the active release and outstanding work. Preserve the results below as
evidence for this earlier pass; they did not themselves authorize production
routing or promotion of practice data.

## Recovery and financial workflows

The latest pre-deployment backup, SHA-256
`30335df13e9ff2b55647845852cc77d5ef1a6d0ed174554342d6c466af2360b9`,
was restored into the new server-only database `rokkad_acceptance_20260924`.
All **117** checked business, retained preference, identity and access-decision
table fingerprints matched. Restore plus comparison took **38.98 seconds**.
This is database recovery time, not full disaster recovery or migration duration.
Existing migrations and restricted-runtime/forced-RLS checks passed.

Using the ordinary owner and restricted database role, one imported active loan
from each of JCL, JSK and Lakshmi passed:

- Current loan and payment pages, repayment preview, payment covering accrued
  amounts plus a bounded principal reduction, and exact exposure reconciliation.
- Identical payment retry without a second collection; receipt PDF response.
- Payment-bearing opening export reporting restoration support. This pass did
  not independently reimport that export; round-trip coverage remains in the
  existing regression suite.
- Full release after payment, zero remaining exposure, identical release retry
  and release memo PDF response.
- Rejection of payment reversal before the later release; release reversal then
  payment reversal restoring the original exposure; reversed receipt retrieval.
- Loan-number counters unchanged; release counter consumed once even after
  reversal, as required by the existing numbering rule. Transaction rollback
  restored all counters and original loan/event state.

These are **18 page/PDF checks** across three branches. All financial work ran
inside rolled-back transactions in the disposable restored database. Document
storage was container-local; shared R2 objects were not written. Private generated
sample PDFs stay on the server and are not issued production documents. Successful
PDF responses establish rendering, not visual or physical print acceptance.

The reader/editor/collector permission probes also passed **36 page checks** on
the restored copy, including forbidden repayment/creation/edit/release actions
and cross-Workspace access. Synthetic users, roles and grants were rolled back.
This verifies permission behavior, not the real production staff roster.

After all probes, the same **117** table fingerprints still matched in both the
restored acceptance database and the running rehearsal database. No checked
business, preference, identity or access-decision rows changed.

Initial probe failures were corrected in the probe only: the first runner lacked
the collected-static volume, and its first counter assertion incorrectly expected
release numbers to be reclaimed by reversal. No application rule was changed.

## Browser and host review

The existing `rehearsal-admin` browser session survived a fresh page load. The
borrower-code filter returned the two existing practice loans, and loan details
showed the loan/draft dates and prominent ticket button. Phone (390 by 844) and
tablet (768 by 1024) screenshots showed those controls within the viewport.
Temporary viewport overrides and language selection were restored afterwards.
This was a platform-administrator session, not a new ordinary-user or Google login.

Hindi switching renders the existing translated navigation and loan sections,
but several recent labels remain English, including Print loan ticket, Draft
created, Temporary workspace access and Records & reports. Bilingual coverage is
incomplete; do not mark the whole daily journey translated or operator-accepted.
Physical printing remains waived as a merge prerequisite.

The host had approximately 59 GiB free disk and 2.6 GiB available RAM. Web listens
on `127.0.0.1:8000`; PostgreSQL has no published host port. Caddy serves HTTPS and
denies public `/media/*`. UFW is inactive; this pass did not inspect the Linode
cloud firewall and therefore does not certify its SSH source restriction.
Debug and checkout are disabled, secure cookies and HTTPS redirect are enabled,
and current hosted HSTS is 3,600 seconds. Earlier generic HSTS warnings must not
be treated as proof that this hosted configuration has HSTS disabled.

## Remaining work identified at this checkpoint

1. **Authentication/proxy configuration is the next technical increment.** There
   are no Google SocialApp rows or settings-based Google app credentials in the
   running rehearsal configuration. Existing password/session checks do not prove
   the owner's intended Google sign-in. Configure the reviewed callback/client
   privately and complete an ordinary owner login without changing the live app.
2. Current allauth `ALLAUTH_TRUSTED_PROXY_COUNT` is **0**. Two distinct synthetic
   forwarded clients resolve to the same proxy address under the running settings.
   With the inspected single-Caddy/private-upstream topology, explicitly configure
   trust for that one hop, verify incoming spoofed headers are replaced and direct
   upstream access remains blocked, then retest login/rate-limit identity. Do not
   enable arbitrary forwarded-header trust or infer this setting from HTTPS trust.
   [Allauth documents the default and required proxy configuration](https://docs.allauth.org/en/latest/common/rate_limits.html);
   [Caddy documents its forwarded-header spoofing protections](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#defaults).
   This pass identifies the issue; it does not change proxy or application settings.
3. Review actual owner/staff assignments and current lending licences, products,
   rates, series and numbering. Keep TEST records and rehearsal grants out of the
   final fresh target; install the accepted JCL/JSK template bundle there.
4. Review durable production secrets, private media identity, recovery retention
   and a separately approved off-server recovery destination. The owner's current
   instruction is to retain database backups on the server; nothing was exported
   to OneDrive or another service. Same-server restore does not cover server loss.
5. Finish the bounded receipt/memo visual and branch-language acceptance, then
   select the final freeze/opening date and obtain the new complete dump the owner
   will provide. Preserve the overnight opening-date boundary in the
   [cutover runbook](linode-production-cutover.md#opening-date-boundary).

Payment-provider acceptance was deferred with checkout disabled. No real mail,
Google, payment-provider transaction, production DNS change or Git push occurred
during this September 24 acceptance pass.
Private scripts, logs, PDFs and aggregate checks remain under
`/home/rokkad/deploy/rehearsal/final-acceptance-20260924/`.
