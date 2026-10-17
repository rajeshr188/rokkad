---
status: implemented
owner: project
updated: 2026-10-17
tags: [loans, closing, navigation, review]
related: [loan-workflow-release-20261017.md, ../flows/multiple-loan-release.md]
---

# Closing navigation review

The owner reported three production sidebar links after the shared closing
release. Restricted read-only inspection confirms all three on application
`a14b5a7f`, image `60868e8324cb...`. Twelve sidebar renderings use the ordinary
permission/context processors across JCL, JSK and Lakshmi, covering release list,
staff guide, batch history and shared closing entry. Labels, destinations and
active states are identical across the Workspaces. Desktop and mobile layouts
include the same sidebar partial. No customer records are exported or modified;
the inspection reports only navigation/source metadata. This is a server-rendered
navigation issue in the released source, independent of browser cache.

## Findings

| Visible link | Actual destination | Finding |
| --- | --- | --- |
| Releases | `pawn_release_list`, `/loans/releases/` | Canonical per-loan release records, including standalone and grouped records, full/partial and reversed history. Already contains the shared Close / release entry action. |
| Completed closures | `paper_closure_guide`, `/loans/releases/paper/guide/` | Opens the staff guide headed “Closing one or several loans”; the label suggests a distinct transaction/history screen. |
| Release batches | `release_batch_list`, `/loans/releases/batch/` | Queries only `PawnReleaseBatch`. The page heading says “Closure history” while its browser title and sidebar still say “Release batches”. |

The previous release consolidated closing selection and saved-contract checks,
but retained the old navigation structure. These links mix transaction records,
help and submission grouping at the same level, suggesting three closing flows.

The batch screen is not complete release history: shared current single closing
uses the ordinary single release writer without creating a batch. Such standalone
release records remain in Releases and do not appear in batch-only history.
The shared closing header and generic browse toolbar currently link to that
batch screen as “Closing history”; the Loans directory calls it “Release batches”.
Renaming batch-only history to general closure history does not resolve coverage.

The generic `loans/browse/list.html` toolbar also appears on Collateral, since
both directories share that template. Release-specific tools should be considered
in the navigation change rather than added globally to every browse page.

Evidence is in `templates/components/navigation/sidebar.html`,
`templates/loans/browse/list.html`, `templates/loans/batches/history.html`,
`templates/loans/pawn/list.html`, `templates/loans/closing/_selection.html`,
`apps/tenant_apps/loans/browse.py`, and the closing/release-batch web modules.

## Recommended smallest coherent change

Keep one **Releases** sidebar destination, using the existing canonical release
directory as its default. Give it a clear **Close / release loans** primary action
that retains the existing explicit current/completed selection for one or many
loans. Present **All releases** and **Grouped submissions** as secondary views
within this area; group records retain links to each individual release.
Move the staff guide to **Help with closing** within the same area. Keep owner
completed-recording restrictions accessible through the existing authorized setup
or contextual control link. Remove the two competing sidebar destinations and
use consistent headings, browser titles and contextual links.

Do not create another closing service, new financial table, replacement history
or synthetic batches for standalone records. Current combined collection and
completed independent settlements keep their distinct evidence meanings. Retain
all old URLs, receipts, CSVs, reversals/corrections, groups and tenant/permission
checks. History visibility requires data-view access; the action retains release
permission and commercial/lifecycle write checks.

Acceptance should cover desktop/mobile navigation, owner and read-only roles,
canonical history containing a standalone current release plus grouped current
and completed releases, correct source-mode labels without inferring loan entry
method, legacy bookmarks, active navigation and the common closing entry action.
Existing posting/calculation services remain unchanged.

## Local implementation

The approved navigation correction is implemented in the maintained release
worktree. One sidebar link stays active across all release routes, including
legacy single-loan closing. Shared contextual links expose All releases, Grouped
submissions and Help with closing. Grouped history explains its limited coverage.
Release actions retain permission/write checks; Collateral no longer inherits the
release toolbar. Owner recording controls are available from the guide as well as
completed-entry context. No URL, writer, model, receipt or financial service is removed.

The owner additionally requested distinct searchable selectors: **loans** for
closing and **Parties** for relationships. The closing picker already used AJAX
Select2; it now has explicit search instructions, Party-code matching, a typed-query
prompt and wrapping selected labels. It continues to search ACTIVE loans with
outstanding collateral only. Selected loans survive a mode change, while the
existing fresh-review requirement and 20/50 limits remain in place.

Relationship add/edit replaces the unbounded plain Party dropdown with a scoped
PartyAutocompleteWidget subclass and its own edit-authorized stateless endpoint.
Tokens bind source identity and Workspace URL, with the existing expiry. Search,
selected labels and pagination reuse Party behavior; queryset validation still
rejects foreign/self selections. Existing relationship status eligibility is
retained, rather than borrowing origination's active-only eligibility.

Interactive Chromium checks found an existing shared `.select2-container` width
rule also sizing the absolutely positioned dropdown wrapper to viewport width.
Narrowing it to `select + .select2-container` keeps selection controls full width
without causing horizontal overflow when either search dropdown opens. No new
JavaScript dependency, widget cache, schema or configuration is introduced.

Python baseline formatting for the four existing Party files is separately retained
in ignored `.tmp/search-formatting-only.patch`, with pre/post AST equivalence checked;
behavior can be reviewed against `.tmp/search-format-baseline/`.
Validation passes: 121 tests in 143.240 seconds covering Party UI, relationship
search and isolation, closing/concessions, release batches and restricted-role
guards. Two browser tests cover 38 desktop/mobile page combinations (20 closing/
navigation/relationship and 18 origination), with no page exceptions or horizontal
overflow. Browser checks type queries, select two loans, remove one, retain selections
across a mode change while disabling stale confirmation, and select/edit a related
Party. The real authorized endpoint responses are exercised separately in Django;
Chromium uses those fictional fixture responses with all network requests intercepted.

Ruff and Black on all eight changed/new Python files pass, along with 2,688 local
documentation links across 773 files, all 22 preserved document originals, supported
app boundaries, repository hygiene and diff whitespace. The local test log is
`.tmp/closing-navigation-regression.log`; browser evidence is in
`outputs/closing-navigation-20261017/checks.json` and the existing origination
browser artifact directory. Formatting-only and behavior patches remain separate.
This checkpoint has not been committed, pushed or deployed.
Private inspection helpers and de-identified output remain in ignored
`.tmp/closing-navigation-review-20261017/`; browser artifacts use fictional data only.
