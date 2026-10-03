---
status: active
owner: project
updated: 2026-09-29
tags: [platform, operations, administration, fw-010]
related: [../architecture/control-plane-contracts.md, ../implementation/onboarding-monitoring.md, ../implementation/platform-mail.md]
---

# Platform administrator console

Open **Platform console** in the signed-in navigation, workspace-manager sidebar
or Django-admin header. Its canonical address is `/app/platform/`. The permanent
platform administrator uses the existing `admin@rokkad.com` sign-in. Workspace
Owner/Admin roles and ordinary Django staff status do not grant console access.

## Daily journey

1. Review the overview: all workspaces, operationally active workspaces, suspended
   workspaces, trials ending within seven days, missing subscription records and
   invitation-email outcomes needing review. Counts include tests and historical
   mail problems; they are not paying-customer or infrastructure-health metrics.
2. Open **Workspaces**. Search by name, slug or owner email, optionally narrowing
   lifecycle and review focus. Results paginate at 25. The system public placeholder
   is excluded; archived, suspended and deletion-pending metadata remains visible.
3. Open a workspace to read its current access explanation. Operational lifecycle,
   recorded subscription and effective access are separate. An active workspace can
   be read-only; a missing subscription can coexist with a dated administrator grant.
   Current access always comes from the existing `workspace_activity` policy.
4. Use **Overview**, **Invitations** and **Access history** tabs to inspect owner
   verification, membership count, invitation/mail outcomes and recent administrator
   decisions. Invitation acceptance does not establish current membership; delivered
   mail does not establish that the recipient opened it. Invitations paginate at ten.
5. Follow the existing management link when action is necessary. For active
   workspaces, settings, team, billing and access-extension links retain their
   destination permissions, explicit Workspace context and audit behavior. Archived
   workspaces link to the existing restore list through `/app/workspaces/archived/`.
   Active workspaces offer **Review suspension**; suspended workspaces offer
   **Review restoration**. Deletion-pending workspaces retain the restriction and
   audit link. Never edit lifecycle directly in Django admin to bypass the existing
   reasoned transition service.
6. Return and refresh to verify a change. Use **Onboarding report** for the existing
   account/trial/team evidence report and **Operator guide** for in-app instructions.

## Boundaries

Console browsing is GET-only; deliberate lifecycle changes use reviewed POSTs.
Both require an active platform superuser,
global request context and no active database Workspace context. Responses disable
caching. It reads control-plane metadata and does not query borrower records, loan
balances or private media. Invitation keys, delivery keys and arbitrary audit JSON
are not displayed. Every workspace-management link continues to act as the actual
signed-in operator; no impersonation, new roles or permission grants are introduced.

The directory evaluates canonical access only for its current page, rather than
loading all workspaces or duplicating billing policy in SQL/templates. Review counts
are database aggregates/existence checks. Invitation membership lookups are batched
and case-insensitive. Mail review signals include failed, unknown, bounced,
complained and suppressed invitation deliveries; account and receipt failures remain
in their existing operator procedures. Refresh the page for a new snapshot.

## Delivery and follow-up

FW-010 now covers oversight, discovery, links to established workflows and guided
suspension/restoration. Delegated support roles, a comprehensive operator action
matrix, ownership recovery screens, support tickets and storage/billing management
remain separate work. Existing advanced-admin capabilities are not certified as safe
service-backed workflows merely because the console links to Django admin.

Validation: 16 focused console, onboarding-report and canonical-route tests passed
with restricted-role boundary checks. Coverage includes non-admin/inactive/context
denial, GET-only/no-store responses, read-only queries, lifecycle/grace/extension
semantics, filtering, pagination, bounded queries, invitation expiry and secret
exclusion. Desktop and 390px mobile browser review used fictional, transaction-local
data; search and tabs passed with no document-level horizontal overflow.

Deployed on 29 September as `rokkad:platform-console-20260929-980dd0c5cfe5`.
Nine production pages rendered inside restricted READ ONLY transactions, ordinary
users were denied, and source/configuration checks passed. Live trials and mail
remain enabled; paid checkout/recurring remain disabled. Only the web image changed.
Private server release evidence and rollback files are under
`/home/rokkad/deploy/cutover-20260924/platform-console-20260929/`.

## Suspend or restore a workspace

1. Open the workspace overview and choose **Review suspension** (active) or
   **Review restoration** (suspended).
2. Check its name, slug and owner. Suspension blocks business screens for everyone,
   including the owner, while retaining existing records. Established recovery
   permissions remain available; suspension is not deletion or cancellation of billing.
3. For restoration, read **If restored now**. This is the normal access policy
   evaluated as though operational suspension were removed. An expired trial may
   therefore return to read-only access; a still-valid extension continues for its
   remaining period. Missing commercial setup can remain recovery-only.
4. Enter an operational reason without borrower details or secrets, type the exact
   workspace slug, acknowledge the impact and confirm. Cancel makes no change.
5. Verify the new lifecycle/current-access summary. **Access history** separately
   shows the latest ten lifecycle changes and ten subscription access decisions,
   with actor, time and reason. The audit link provides older records.

Reviews expire after 15 minutes. Changed details require a fresh confirmation;
the reason is preserved but acknowledgement and typed confirmation are cleared.
Repeated successful submissions cannot repeat a transition. Neither action sends
email, extends trials, grants paid access, changes subscription dates or mutates
loan/payment/media records. Subscription access can naturally change after review
as its own expiry dates pass; the current summary remains authoritative.

Implementation: `platform_lifecycle` checks global active-superuser authority,
locks the target and delegates to the existing atomic lifecycle/audit service.
There is no migration, new role, new permission or impersonation capability.

Lifecycle increment deployed on 29 September as
`rokkad:platform-lifecycle-20260929-d1caed09cb6d`. Thirty-seven focused console and
lifecycle tests passed, including restricted-role authorization, CSRF, changed/
expired/tampered/replayed confirmation, unchanged subscription evidence and audit
rollback. Fictional desktop/mobile review and 15 restricted READ ONLY production
page renders passed. Seven source hashes, preserved configuration, anonymous HTTPS
and mail health passed. No real workspace lifecycle was changed for verification.
Release/backup/rollback evidence remains private on the server under
`/home/rokkad/deploy/cutover-20260924/platform-lifecycle-20260929/`.
