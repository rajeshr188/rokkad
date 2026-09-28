---
status: accepted
owner: project
updated: 2026-09-27
tags: [billing, subscriptions, authorization, cancellation]
---

# Owner authorization and stopping renewals

The next FW-019 increment exposes an owner page for operator-prepared Test Mode
agreements. Creation remains the explicit durable operator command: there is no
new HTTP exception to Workspace transaction/RLS middleware and no new launch
duration. The page displays frozen price, tax, member count, frequency and maximum
cycle count before authorization. At completion the mandate ends; purchased access
then follows the existing grace/read-only policy. New authorizations remain behind
the default-off recurring flag. Live keys are rejected by the action services.

Checkout receives the saved provider subscription identity. Its callback verifies
HMAC over payment ID and the **server-held** subscription ID, then fetches the
agreement. A verified callback is append-only and idempotent; it cannot create paid
access, invoice, payment or receipt. Signed paid-cycle evidence remains the sole
granting path. A failed browser confirmation retries that same callback instead
of opening another Checkout. Refresh and known-invoice recovery continue when new
authorizations are paused. Canonical ownership and explicit Workspace context
are checked at the service boundary, including before storing remote observations.
Owner, operator and webhook status writes recheck the locked agreement so a delayed
nonterminal observation cannot reopen a terminal mandate. Late financial evidence
can still be recorded for a closed agreement with access held for review.

"Stop future renewals" cancels the provider mandate immediately
(`cancel_at_cycle_end=false`), **without** changing the local paid period or
Subscription status. This avoids depending on an ambiguous scheduled cancellation
indicator. This action is not a refund and a cancelled mandate cannot be resumed.
In-flight payments still require settlement reconciliation. Provider cancellation
does not release the Workspace reservation or approve a replacement agreement.

Save `cancel.requested` under the shared Company lock. Django `on_commit` makes a
bounded delivery attempt only after that request commits; rollback cannot contact
the provider. The delivery service refuses an enclosing transaction and commits
`cancel.dispatched` under the same lock before its first provider read/POST.
Concurrent delivery and any later recovery may only GET once this claim exists.
Validate remote identity before cancellation and independently fetch the result.
Only a verified terminal state is displayed as ended. Timeout, malformed response,
crash before POST or failed local persistence retains the reservation and visible
uncertainty. No automatic second cancellation is sent, even if the first may not
have reached Razorpay. Existing append-only AgreementEvent evidence is sufficient;
no generic queue framework or new table is introduced.

The explicit recovery command can deliver an undispatched saved request, or fetch
a dispatched outcome. A process crash between request commit and callback execution
therefore remains recoverable. There is no background scheduler or automatic retry.
An original actor who has lost ownership/active status cannot dispatch a saved
request; the current owner can refresh evidence, and an operator must resolve the
provider action explicitly. This conservative recovery is a rehearsal limitation.

The isolated review settings serve source static assets with WhiteNoise finders so
the current JavaScript and styles are available with DEBUG off. Production static
settings and deployment remain unchanged.

Real recurring provider acceptance, self-service creation/duration selection,
scheduled conversion of existing paid/trial terms, financially reconciled
reservation release and recurring refund access decisions remain separate work.

Provider contracts checked 2026-09-27:
[Checkout signature and subscription integration](https://razorpay.com/docs/payments/subscriptions/integration-guide/),
[immediate cancellation and terminal state](https://razorpay.com/docs/api/payments/subscriptions/cancel-subscription/),
[local source asset serving](https://whitenoise.readthedocs.io/en/stable/django.html#whitenoise-use-finders).
These document the contracts; they do not prove acceptance on this merchant account.
