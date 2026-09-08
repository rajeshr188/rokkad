---
status: implemented
owner: project
updated: 2026-09-08
tags: [navigation, ux, workspace, account, saas]
related: [project-wide-ux-revamp.md, ../architecture/control-plane-contracts.md, ../STATUS.md]
---

# Workspace navigation simplification

## Implementation checkpoint

The operator authorized implementation. The switcher uses `request.workspace`
for its label and selection, global pages use Workspaces, and Clear Workspace is
removed from normal navigation. Login landing alone uses the validated saved
preference; the list always renders. Creation and onboarding completion target
explicit setup URLs, still subject to existing billing recovery. The global
landing no longer forces onboarding before incoming invitations can be viewed.
The existing dashboard behavior still remembers the last visited Workspace;
opening personal pages does not clear or change that preference. It never
determines the scope of an already-open Workspace tab.

Both app and administration layouts include the same Workspace navigation.
Settings groups team, billing, loan setup, documents, preferences, security,
and data tools, using normalized request-scoped action permissions. Personal
pages use a personal sidebar and a compact account menu. Duplicate Workspace
management/membership routes redirect to the single list. Unsaved inputs trigger
a confirmation on Workspace switching; cancelled switches retain the edits.

Compatibility clearing routes and old templates remain for existing callers;
they are not offered as part of the normal flow. Two internal layout templates
remain to preserve existing content blocks, with one shared navigation component.
Switching opens the destination overview rather than transferring record IDs.
No database schema, row policies, payment, or lending command was changed.

## Recommendation

One authenticated application experience with two explicit scopes: personal
account and the Workspace identified by the current URL. Team, billing, setup,
and business apps belong to that Workspace. Visiting account pages does not
require clearing the saved Workspace preference. This is a presentation and
routing simplification, not a replacement for membership, authorization, lifecycle,
billing recovery, or forced RLS.

## Findings before implementation

- `templates/components/navigation/workspace_switcher.html` reads
  `request.user.profile.workspace` for its label and active item. That is a saved
  preference, not the authority of the displayed page. Different explicit
  Workspace tabs can consequently show a misleading selected label on reload.
- `accounts/views.py:clear_workspace` clears that preference and redirects. It
  does not end membership or provide a security boundary. Its menu placement
  still suggests an enter/exit mode.
- `layouts/workspace.html` and `layouts/management.html` expose different
  navigation structures even for routes under the same Workspace slug. The
  management sidebar mixes Workspace creation, target-Workspace settings,
  team, billing, and personal account links.
- The account dropdown duplicates profile editing, security actions, memberships,
  Workspace management, and billing destinations.
- `workspace_selector` automatically redirects to the saved Workspace unless
  `show_all` is supplied; `workspace_management` provides another listing surface.
  Explicitly opening a list should never immediately leave that list.
- Workspace creation sets a preference then traverses list/selector redirects.
  Onboarding has its own completion path to setup. Unify the user-facing outcome
  while retaining the existing creation service and its guarantees.
- Team/settings/billing already have Workspace-specific routes. Their separate
  management presentation is not required by the isolation architecture.
- Navigation still checks legacy permission strings and role names in places.
  Reuse the target Workspace's action policy when consolidating navigation;
  hidden links are not authorization and server enforcement must remain.

Evidence: `accounts/views.py`, `apps/orgs/views.py`, `apps/onboarding/views.py`,
`pages/views.py`, `templates/components/navigation/`, and the two layouts.
This review is source-based; it does not claim a fresh interactive session in
real user accounts or a complete audit of every legacy route.

## Proposed information architecture

One header: Rokkad, Workspace switcher, user menu. No second management banner,
repeated identity, Clear Workspace, or duplicate Enter link.

Workspace sidebar:
- Overview
- Counter / New loan
- PawnLoans
- Parties
- Rates
- Notifications
- Settings

Settings sections:
- Business profile
- Team: Members and Invitations tabs; Invite member is an action
- Billing: subscription, plans, invoices (authorized billing roles only)
- Loan setup: licenses/series, economics, products
- Documents and printing
- Preferences and supported app configuration
- Security and archive: retain explicit permissions and confirmation flows

Keep a contextual Setup shortcut on loan pages and setup blockers. Operational
queues such as notices, custody checks, and physical verification belong under
Loans/operations; storage-location definitions and print profiles belong in setup.
Avoid burying routine work inside administrative configuration.

Personal menu:
- My account (profile, email, password, connections, personal preferences)
- My invitations (invitations received across Workspaces)
- Sign out

Workspace switcher:
- Accessible Workspaces; current URL Workspace is selected
- All Workspaces (always displays the list)
- Create Workspace

All Workspaces replaces duplicate workspace-management and membership overviews;
its cards show each membership role and authorized management actions. It is a
personal global page with no active data-plane context. Archived Workspaces can
remain a secondary destination for users allowed to recover them.

## Expected journeys

1. Sign in with an invitation or valid deep link: preserve the target through
   authentication and access validation. Do not override it with last Workspace.
2. No Workspace: present incoming invitations and Create Workspace; do not force
   invited staff to create a business first.
3. Returning user: valid saved Workspace -> its landing page; one accessible
   Workspace can be a default; multiple without a valid preference -> chooser.
   Validate membership and lifecycle before redirecting.
4. Create bgh: redirect directly to `/w/bgh/...` setup; header immediately shows
   bgh from request authority. Team invitation is optional. Distinguish the
   general setup checklist from lending prerequisites; completing the former
   must not imply that loan origination is ready.
5. Manage bgh team or billing: use Settings without leaving bgh or changing the
   header/sidebar identity. Return to Loans directly.
6. Open My account: show a personal page; preserve the navigation preference but
   do not treat it as active Workspace authority. On global pages label the
   switcher Workspaces; a last-used Workspace may be described explicitly as such.
7. Switch to jcl: safe landing in jcl. Preserve list-level destinations only when
   mapped explicitly and authorized; never carry a bgh loan/member/invoice ID.
   Warn about unsaved forms before switching. Other open tabs retain their URLs.
8. Incoming invitation: account-level acceptance -> invited Workspace after
   validation. Sent invitations remain in that Workspace's Team section.
9. Expired subscription: retain authorized billing recovery access; normal app
   operations still follow commercial/lifecycle rules. Removed membership should
   show a clear access outcome and a route to the remaining Workspace list.

## Implementation order and acceptance

1. Fix switcher identity, remove the Clear action from normal navigation,
   separate the login landing decision from the always-visible Workspace list,
   and make create/accept redirects explicit. Keep compatibility routes where useful.
2. Unify the Workspace and administration shell. Group settings and account
   destinations; consolidate duplicate list screens and labels.
3. Align onboarding, invitation, recovery, and empty states with these destinations.
4. Verify two simultaneous Workspace tabs; owner/admin/staff visibility and denial;
   account pages with/without a saved preference; new and invited users; create
   bgh while previously using jcl; billing recovery; unsaved switch cancellation;
   mobile and keyboard navigation. Retain RLS and HTTP operator acceptance.

No data migration or tenancy redesign is needed for this proposal. Renaming the
legacy profile field can be a separate cleanup after all its callers are reviewed.
Implementation was authorized after the analysis and published as `df26e6b`.

PostgreSQL policies govern row access, not how many menus an application has:
https://www.postgresql.org/docs/current/sql-createpolicy.html . The repository's
accepted control-plane contracts determine the application-specific scope rules.
