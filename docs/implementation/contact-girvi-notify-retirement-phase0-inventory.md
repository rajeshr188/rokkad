---
status: active
owner: project
updated: 2026-08-16
tags: [contact, girvi, notify, notify-v2, party, loans, dea, inventory, retirement]
related:
  - ../adr/2026-08-16-retire-contact-girvi-and-legacy-notify.md
  - ../plans/contact-girvi-legacy-notify-retirement.md
---

# Contact, Girvi, And Legacy Notify Phase 0 Inventory

## Baseline

- Branch: `no-tenants`.
- `python manage.py check`: passes with zero issues.
- Django currently loads 253 models/registered objects in the shell baseline.
- A broad text inventory found 141 files outside the Girvi package containing
  Girvi/GivenLoan/TakenLoan vocabulary. This includes runtime, tests, templates,
  migrations, and intentional historical text; it is a discovery count, not a
  deletion count.
- Combining Party and Notify v2 app labels in one Django test invocation fails
  before tests run because Python resolves the generic `tests` package from the
  wrong app. Focused suites must be invoked separately until test discovery is
  normalized.
- The Party suite did not complete inside the 120-second baseline window.
- Notify v2 baseline: 29 tests, 21 pass and 8 error. The errors expose current
  dependencies on legacy `notify.access` and Girvi access decorators rather
  than retirement changes. Model drift is also reported for DEA.

## Selected Dispositions

| Legacy capability | Disposition | Target |
| --- | --- | --- |
| Contact identity/customer/supplier | Replace | Party identity and roles |
| Girvi GivenLoan | Replace/retire | Loans PawnLoan; omit non-selected compatibility behavior |
| Girvi TakenLoan/repledging | Replace | Loans FundingLoan and funding collateral workflow |
| Girvi notices/reminders | Retire | Remove Girvi producers; retain generic Notify v2 |
| Legacy Notify generic delivery | Replace | Notify v2 |
| Girvi DEA effects | Retire | Remove source-specific rules after source retirement |
| Posted accounting evidence | Preserve or reset as a whole | Never mutate selectively |

Loans already contains persisted `FundingLoan`, terms, collateral, event,
repayment, closure, document, selector, and service implementations. Girvi does
not need to remain merely to preserve a lender-funding aggregate.

## Concrete Runtime And Model Blockers

### Contact

Surviving concrete model fields still point at Contact:

- `dea.Account.contact -> contact.Customer`;
- `dea.PurchaseInvoiceVoucher.vendor -> contact.Customer`;
- `dea.SalesInvoiceVoucher.customer -> contact.Customer`;
- `product.Price.contact -> contact.Customer`;
- `notify_v2.NotificationRecipient.customer -> contact.Customer`;
- `party.Party.legacy_customer -> contact.Customer`.

DEA filters/account resolution, Product forms/pricing, Party bridge/forms, Orgs
dashboard selectors, and many characterization tests also import Contact.
Contact cannot be uninstalled until these fields and callers have Party-owned
replacements.

### Girvi

The wrong-direction DEA imports are:

- `dea.services.pre_close -> girvi.facade`;
- `dea.views.period -> girvi.facade`.

Girvi also remains visible through Orgs proxy views/routes, Party portal
selectors, Contact metrics/actions, onboarding, permissions, navigation,
configuration, Notify v2 batch behavior, templates, seeds, and route-intent
tests.

Girvi owns the concrete forward relationships to DEA/Party/Product, while those
apps expose reverse relations at runtime. Important edges include
`LoanInterestAccrual.journal_entry_voucher -> dea.JournalEntryVoucher`, loan
party links, and loan-item product-variant links. Removing Girvi models removes
the reverse relations automatically, but only after every caller stops using
them.

### Legacy Notify

Surviving direct runtime dependencies are narrow but critical:

- Notify v2 imports its authorization decorators from `notify.access`;
- Orgs proxies legacy Notify views;
- tenant default seeding imports legacy notification models;
- Party operational tests read legacy notification evidence;
- Girvi tasks/facades/adapters produce or count legacy notifications.

Girvi producer deletion removes most of the legacy surface. Notify v2 must own
its authorization boundary before legacy Notify can be uninstalled.

## Migration Graph Blockers

Contact migration nodes are dependencies of surviving apps:

- DEA initial and later purchase/Party-account migrations;
- Product `0002_initial` and pricing constraints;
- Notify v2 `0001_initial`;
- Party compatibility-era state through Contact's Party bridge.

Notify v2's initial migration creates a nullable `customer` FK to
`contact.Customer`. DEA migrations create multiple Contact-backed fields.
These historical nodes prevent physical deletion of the Contact migration
package until a clean surviving-app baseline is built or tombstone migrations
are deliberately retained.

Girvi migrations depend on DEA, including the interest-accrual journal link;
DEA has no migration dependency on a Girvi model. DEA's Girvi-named seed
migrations are internal DEA nodes and must remain loadable until the final clean
baseline.

## Freeze Boundary

Effective with the accepted retirement ADR:

- no new features may be added to Contact, Girvi, or legacy Notify;
- do not extend Girvi event-driven DEA scaffolding;
- do not add new Contact fallbacks or Customer foreign keys;
- do not add new legacy Notify producers;
- new identity work uses Party;
- new loan work uses Loans;
- new notification work uses Notify v2.

Runtime write shutdown and physical job disabling belong to later reviewed
code/configuration slices; Phase 0 itself does not change runtime behavior.

## Phase 1 Entry Gate

Phase 1 may begin because:

- the retirement ADR is accepted;
- Contact, Girvi, and Notify dispositions are explicit;
- FundingLoan has a target owner in Loans;
- baseline startup and known test failures are recorded;
- the migration blockers are known.

The exact destructive database command remains a Phase 7 approval boundary.
The selected strategy is a clean development baseline, but no existing database
may be dropped merely because this inventory exists.

## Phase 1 Progress

The first Party cutover slice is complete in code:

- Product `Price` overrides now reference `party.Party`, and the resolver,
  forms, admin, views, templates, and characterization tests use Party.
- Product migration `0015` backfills through `Customer.party` and fails closed
  if a legacy price has no Party mapping.
- Notify v2 `NotificationRecipient` no longer stores a Contact FK. Its optional
  Party link remains appropriate for generic/system recipients, while Girvi
  batch recipients use the borrower's Party when available.
- Notify v2 migration `0006` refuses to discard a legacy Customer association
  that lacks a Party mapping.

Both migrations applied successfully in the focused test database. The targeted
Notify v2 Girvi-batch creation test passes. The Product suite remains
inconclusive because stale tenant rows broke `--keepdb`, and rebuilding the test
database exceeded the 180-second command window; no Product assertion failed.

- Notify v2 authorization is now locally owned by `notify_v2.access`; active
  Notify v2 views no longer import `notify.access`. Four focused tests preserve
  workspace membership, view, send, and unknown-action fail-closed behavior.
  This completes the shared-authorization portion of Phase 3 without deleting
  legacy Notify or changing its remaining callers.

- Notify v2's active batch list/detail surfaces are domain-neutral and retain
  existing delivery evidence without linking back to Girvi or legacy Notify.
  The Girvi-only on-demand PDF route and default tenant seed rows are removed.
  The Girvi producer adapter and dormant renderer/service remain paired for the
  next slice; deleting only one side would make the installed Girvi URL surface
  fail during import.

- The paired producer boundary is now removed: Girvi has no notice creation
  routes, bulk action, selector action, or auction-transition notification side
  effect, and Notify v2 no longer contains or exports the Girvi batch service or
  PDF renderer. Historical Notify v2 evidence is retained; this is a runtime
  deletion only and performs no destructive data migration.

- Party detail and portal loan summaries now use a Loans-owned Party history
  selector over `PawnLoan.borrower`. Active outstanding values are derived from
  the canonical Loans balance selector; pre-disbursal rows do not invent an
  outstanding balance. The remaining Party portal Girvi dependency is payment
  source discovery and must move to Loans accounting-event evidence.

- Party portal payment discovery now uses DEA PaymentVoucher only for Party-
  owned sales invoices and immutable Loans repayment events for Party-owned
  PawnLoans. Reversed repayment events are excluded. Party runtime code now has
  no Girvi imports.

- Orgs dashboard composition now uses a Loans-owned, workspace-explicit
  PawnLoan summary. Financial totals fold canonical active-loan balances. The
  Girvi-only "sunken" valuation is not translated or approximated. Remaining
  Orgs-to-Girvi dependencies are deep-route compatibility wrappers, not
  dashboard data reads.

- DEA period close no longer reads Girvi loan counts or invokes Girvi accrual
  mutation. Its remaining checklist is DEA-owned. Loans accrual continues to be
  triggered only through its explicit supported workflows; a period-close batch
  command was not invented during retirement.

- Orgs workspace loan compatibility wrappers now call or redirect to canonical
  Loans PawnLoan list, detail, document, reporting, and operations surfaces.
  The module registry and loan chooser no longer advertise Girvi, and the
  workspace numbering alias now opens Loans-owned license/series setup. Public
  workspace route names remain stable during the cutover.

- Legacy Notify URL names remain resolvable for bookmark compatibility, but
  every route now redirects to the Notify v2 batch list instead of importing a
  legacy view. Orgs notification aliases and remaining shared menu links also
  open Notify v2. Legacy IDs are intentionally discarded because they do not
  identify Notify v2 batches. The legacy app remains installed only while
  Girvi runtime imports and default-data seeding still depend on its models.

- Tenant seed commands no longer import legacy Notify, advertise
  `--skip-notify`, schedule `seed_notify`, or forward that option across all
  schemas. Notify v2 is the only notification seed action and deliberately
  seeds no workflow-owned defaults. The unreachable legacy seed method bodies
  have also been physically deleted.

- Girvi runtime no longer imports legacy Notify, queries NotificationItem, or
  prefetches/reads the legacy generic notification relation. Girvi dashboard,
  detail, operational queue, and facade output retain neutral empty/zero notice
  presentation during retirement. The existing `one_year_reminder` Celery task
  name remains as a fail-safe disabled entry point for stale schedules; it does
  not create Notify v2 work. Supported notices remain Loans-owned intents.

- Legacy Notify is now physically retired. Its installed-app entry, source
  package, migrations, templates, tests, JPEG asset, and obsolete shared
  `utils/loan_pdf.py` module are deleted. A project-owned compatibility URL
  module preserves old route names as redirects to Notify v2 batch history and
  discards incompatible legacy IDs. Notify v2 is the only notification app in
  the active migration graph.

- Girvi is now physically retired. The Django app, migrations, URLConf, source,
  templates, graph artifacts, and Girvi-only root validation scripts are
  deleted. Global navigation targets Loans, Contact's temporary active-customer
  metric counts Party-bridged active PawnLoans, and every `/girvi/...` bookmark
  is handled by a project-owned catch-all redirect to the PawnLoan list. No
  Girvi app participates in the active migration graph.

- Orgs dashboard customer metrics now come from Party rather than Contact.
  Active CUSTOMER roles define the customer population, Party creation dates
  drive registration history, and Party-linked PawnLoans define active-loan
  customers. Global and workspace navigation now opens Parties. Orgs runtime
  has no Contact import.
- Loans borrower-accounting setup now resolves the DEA borrower receivable
  mapping directly from `PawnLoan.borrower`. It no longer invokes the Party-to-
  Customer bridge, creates a compatibility Customer, or exposes Customer data
  in its result/audit contract.
- Party portal invoice selectors now use required invoice Party ownership only.
  Party detail removed its dead legacy-Customer/Girvi activity adapter and uses
  the Loans-owned Party history summary for loan counts.
- The interactive Customer conversion endpoint is removed. The customer bridge
  service, one-time backfill command, and compatibility tests are also removed.
  Party merge no longer treats legacy Customer links as a conflict or transfers
  them. DEA's account runtime and Party export no longer read those links.
- `dea.0047` removes the concrete `Account.contact` FK after required Party
  ownership and Party-only account resolution were established. DEA Account
  runtime no longer has any Contact identity field.
- `dea.0048` removes the legacy sales-invoice `customer` and purchase-invoice
  `vendor` FKs and their indexes. Both invoice aggregates and their posting
  account resolvers now require Party directly.
- Contact's tenant URLConf is unmounted. A project-owned catch-all preserves
  bookmarks as Party-list redirects while the installed app remains solely to
  satisfy historical migration dependencies before baseline reconstruction.

The second Party cutover slice establishes Party as the DEA account write owner:

- `DEA.Account.party` is required; its legacy Contact link is nullable migration
  evidence and is no longer required to create an account.
- `dea.0044` backfills Account through `Customer.party` and fails closed on any
  unmapped account.
- Party account resolution can create accounts for a Party with no legacy
  Customer bridge.
- Account selection, filtering, primary account views, aging views, period
  reports, opening-balance presentation, and commodity business-event Party
  consistency checks now use `Account.party`.
- The unmanaged balance-view models still expose legacy `contact_id`; rebuilding
  those SQL views for Party is required before Contact can be physically removed.

Django checks, Python compilation, migration graph checks, and model drift checks
pass. The focused database suite exceeded 180 seconds while preparing the tenant
test state and produced no assertion result.

The DEA derived-balance slice is also Party-based in code:

- unmanaged `AccountBalance.party` replaces its Contact relation;
- `dea.0045` drops/recreates `account_balances` with `dea_account.party_id` and
  contains reverse SQL restoring the legacy Contact projection;
- dashboard top-debtor/top-creditor reads and templates now consume Party.

The migration graph and state checks pass. Plain `sqlmigrate` cannot render the
tenant-app SQL because the configured tenant router reports the operation as a
no-op outside a tenant-schema migration. The migration subsequently executed
successfully through the Django tenant test runner. A direct balance-view
characterization test exceeded 120 seconds during tenant setup and returned no
assertion result, so numeric view reconciliation remains a fresh-database gate.

Sales and purchase invoice writes are now Party-owned:

- Party is required on both invoice models and is selected by forms/admin;
- Customer/vendor FKs are nullable, `SET_NULL` migration evidence only;
- list/search/detail/report surfaces use Party;
- posting rules use version 3 Party-based fingerprints;
- `dea.0046` backfills missing Party ownership and fails closed for unmapped
  legacy counterparties.

Migrations `0044`, `0045`, and `0046` executed successfully in the test
database. All six focused sales/purchase resolver and posting-rule tests pass,
including Party fingerprint assertions.
