---
status: active
owner: project
updated: 2026-06-21
tags: [status, architecture]
related: [ROADMAP.md, plans/completed.md, plans/active.md]
---

# Status

## Current Shape

Rokkad is moving toward a layered architecture:

- Domain apps own their business concepts.
- DEA owns accounting documents, vouchers, voucher lines, journal entries, posting rules, and period locking.
- Cross-app integrations should go through facades, selectors, or use-case services rather than direct model imports.
- Girvi loan operations are being moved toward command/use-case classes, with accounting effects delegated to DEA.
- Contacts are being separated from loan-specific reads through summary selectors and Girvi facades.

## Recently Stabilized

- Contact stale loan references were removed or routed behind selectors/facades.
- Girvi dashboard and loan list now target `GivenLoan` / `TakenLoan` instead of legacy loan models.
- DEA facade boundaries were split internally and protected with architecture import tests.
- Girvi introduced a facade for cross-app reads.
- Rates are exposed in navigation/dashboard paths, with visible rate-source setup.
- Girvi disbursal can self-heal missing voucher types and ensure customer accounts before posting.
- Dashboard numeric values such as pure weight and current value are formatted to two decimal places.
- Agent-facing documentation was split by purpose: root `AGENTS.md` now contains operating rules, `docs/AGENT_MEMORY.md` contains durable project context, and `docs/constitution.md` contains non-negotiable accounting principles.
- Orgs now has a centralized role policy for membership and invitation changes, named integrity constraints for workspace membership/invitations, corrected sidebar permission codenames, and dashboard reads routed through app facades/selectors.
- Party has been accepted as the long-term external entity model. `contact.Customer` remains the compatibility model until a phased bridge and migration are implemented.
- Party Phase 1 is complete: the tenant app skeleton, initial model layer, admin registration, selectors/facade, migration, and model tests were added without changing existing Contact/Girvi/DEA behavior.
- Party Phase 2 is complete: canonical role seed data, an idempotent `seed_party_roles` command, tenant default seeding integration, and seed tests were added. Existing tenant schemas were seeded with the canonical roles.
- Party Phase 3 is complete: the nullable `Customer.party` compatibility bridge, idempotent customer-to-party backfill service, command, tests, and existing tenant backfill were completed.
- Party Phase 4 is complete: DEA now has party-role account mappings, account resolution through the public facade, support for multiple DEA accounts per bridged customer/party, and a `Customer.account` read compatibility alias.
- Party Phase 5 is complete: current Girvi borrower/lender disbursal, repayment, release, auction, sale, and legacy repayment posting paths resolve subledger accounts by role and purpose through the DEA resolver instead of reading `Customer.account` directly.
- Party Phase 6 is complete: DEA sales and purchase invoice posting rules resolve customer receivable and supplier payable accounts through party-aware role/purpose resolution, and those rules now emit the current posting bundle shape.
- Party Phase 7 is complete: the tenant Party UI now exposes list/search/filter, create/edit, detail tabs, role add/end, read-only contact/address/KYC data, DEA party account mapping visibility, and linked legacy customer activity for loans, sales, and purchases.
- Party Phase 7.1 is complete: Party detail now supports profile photo upload/removal plus inline add/edit/delete for contact methods, addresses, identifiers, and documents, with primary contact sync to Party summary fields.
- Party Phase 7.2 is complete: Party contact forms now validate phone/mobile/WhatsApp values, normalize phone numbers to E.164, validate email and website contact values, and expose Party relationship add/edit/delete on the Party detail page.
- Party Phase 7.3 is complete: Party now captures textual identity relations such as `S/o`, `D/o`, `C/o`, and `W/o` with a related person name, including bridge mapping from `Customer.relatedas` / `relatedto`.
- Party Phase 7.4 is complete: Party profile photos can now be captured from a device camera or uploaded from a file on the Party detail page.
- Party Phase 8 is complete: Party UI now supports converting unlinked legacy customers and merging duplicate parties with explicit guardrails for legacy customer links, identifiers, and DEA account mappings.
- Party Phase 9 has started: Girvi loans and DEA sales/purchase invoice vouchers now have nullable Party shadow FKs with bridge backfills and Party-preferred DEA account resolution.
- Experimental operational `sales`, `purchase`, and `approval` tenant apps were removed from runtime on 2026-06-19. DEA `SalesInvoiceVoucher` and `PurchaseInvoiceVoucher` remain in place for monetary accounting while commerce/procurement is redesigned around commodity, inventory, and settlement.
- Cleanup validation passed on 2026-06-19 against a fresh isolated validation database: `migrate_schemas --shared`, tenant schema creation/migration, tenant default seeding, Party operational-link tests, product inventory/pricing tests, and current DEA party sales/purchase posting tests.
- Runtime role seed definitions no longer create or assign the stale experimental sales/purchase permission codenames; DEA invoice vouchers remain covered by DEA permissions.
- Girvi lifecycle language has been canonicalized in runtime code: `GivenLoan` now uses the canonical lifecycle flow, legacy transition names are aliases, and `TakenLoan` has a smaller dedicated lifecycle.
- Girvi app internals were documented under `docs/apps/girvi/`, covering architecture, models, backend workflows, userflows, and refactor priorities.
- Onboarding workspace creation no longer wraps tenant schema provisioning/migration in an outer application transaction, avoiding PostgreSQL pending-trigger failures when DEA seed migrations are followed by `ALTER TABLE` migrations such as `dea.0015`.
- Generic tenant model import/export moved out of Contact into tenant utility data tools, with sidebar visibility for Owner/Admin users and compatibility redirects from the old Contact URLs.
- Party creation now auto-generates tenant-local sequential `P-000001` style party codes when no code is supplied, while preserving manual/imported codes.
- Girvi given-loan creation is now Party-first: the create form selects an active Party, auto-bridges that Party to a compatibility `Customer` on save when needed, stores `GivenLoan.borrower_party`, and keeps the legacy `borrower` field populated for compatibility.
- Party list now supports filtered CSV/XLSX export for Owner/Admin users, using a flat Party export with active roles and compatibility customer linkage.
- Girvi cleanup P1 is complete: broken legacy reminder Celery tasks now fail closed as disabled, item-type averages no longer query the removed `loan_type` field, interest-accrual command output is ASCII-safe for Windows consoles, repledge creation now resolves an active loan series before creating `TakenLoan`, custody runtime helpers no longer import legacy `models.loan` or assume `loan.customer`, custody FKs now have a guarded migration to `TakenLoan`, `RepledgedLoanItem` mutation routes are read-only legacy surfaces, custody return/release behavior has focused guardrail coverage, TakenLoan direct plus queryset amount/weight/value/interest reads now use `RepledgeHistory`, and refactored interest metrics no longer shadow read-only model properties.
- Girvi cleanup P2 is complete: transition aliases remain accepted, primary state/UI/form transition registries now contain canonical entries while legacy-only metadata is isolated in explicit compatibility registries, TakenLoan transition metadata covers activate/settlement states, active list/detail/transition surfaces display canonical lifecycle labels instead of raw legacy statuses, and flow-derived tests verify transition registry metadata against `flows.py`.
- Girvi cleanup P3 is complete for current refactored runtime paths: synchronous Girvi payment, loan posting, accrual posting, repayment view posting, loan journal reads, model payment helper voucher creation, and dashboard payment counts now go through `apps.tenant_apps.girvi.integrations.dea_adapter`, with compatibility wrappers retained for old import/method surfaces.
- Girvi cleanup P4 has started: `loan_detail` display metrics, storage position lookup, interest reporting, and release CTA metadata now come from the detail read-model selector instead of being calculated directly in the view.
- Girvi repayment view orchestration is now service-backed: GivenLoan receipt catch-up accrual, repayment payload shaping, DEA posting delegation, and TakenLoan repayment posting live in `service_modules.repayment`, leaving `loanpayment.py` as form/message/redirect coordination.
- Girvi cleanup P4 is complete: bulk merge/delete selection parsing, guard validation, merge orchestration, and delete orchestration now live in `service_modules.bulk_operations`, leaving `views.loan` as message/redirect coordination for those actions.
- Girvi cleanup P5 has started: deprecated `Loan` / `LoanPayment` are no longer exported from `apps.tenant_apps.girvi.models`; explicit historical access now goes through `apps.tenant_apps.girvi.models.legacy`, stale management command imports were moved to `GivenLoan` where appropriate, legacy payment import/export is labelled as `LegacyLoanPaymentResource`, and architecture tests guard against broad legacy imports.
- Girvi cleanup P5 command-policy pass is complete: legacy manual `do` is runtime-disabled, legacy `missingcol` is opt-in only via `GIRVI_ENABLE_LEGACY_IMPORT_COMMANDS=1`, and guardrail tests enforce both behaviors.
- Girvi cleanup P6 planning has concrete route inventory/matrix coverage in `docs/apps/girvi/url-compatibility-matrix.md`, including canonical-vs-alias mapping for duplicate route names/paths before alias removal.
- Girvi cleanup P6 internal reverse canonicalization has started: base navigation template links now use canonical `girvi_*` storage-box route names, while alias routes remain in place for compatibility.
- Girvi cleanup P7 scaffolding has started: a tenant outbox model/migration for posting events, outbox enqueue helper, and draft Girvi posting event contract payload helpers were added without changing current synchronous posting execution paths.
- Girvi cleanup P7 execution is currently paused by project decision; existing synchronous Girvi to DEA posting remains the runtime path while outbox scaffolding stays in place.

## Known Pressure Points

- MVP cleanup audit has started in [plans/mvp-cleanup-audit.md](plans/mvp-cleanup-audit.md). The experimental sales/purchase/approval runtime apps have been removed under the no-production-data cleanup decision; Girvi cleanup is now proceeding in small verified stabilization slices.
- Girvi lifecycle compatibility aliases should be kept until old bookmarked transition URLs and legacy imported status values are no longer needed.
- Girvi custody database FKs now have a guarded migration from legacy `"girvi.Loan"` references to `TakenLoan`; tenant rollout should use `migrate_schemas`. Legacy manual command policy is now explicit (`do` disabled; `missingcol` opt-in for controlled import/rehearsal), but final P5 closure still needs broader legacy-import guardrails and command lifecycle documentation.
- Event-driven Girvi-to-DEA posting architecture remains accepted direction, but execution is currently paused.
- Some archived docs contain older naming, model shapes, and implementation assumptions.
- More cross-app reads should be audited and moved behind facades/selectors.
- Period-lock validation should remain inside the posting engine for all accounting paths.
- Orgs service extraction is started but not complete; workspace/team mutation views should continue moving toward thin request/response coordinators.
- Party Phase 9 still needs remaining notification document surfaces reviewed before cutover planning, plus additional operational create/edit surfaces beyond Girvi given-loan creation.

Historical assessments are preserved in [archive/root](archive/root/).
