---
status: active
owner: project
updated: 2026-06-25
tags: [dea, accounting, commodity, business-events, checkpoint]
related:
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - dea-business-event-form-preview-contract.md
  - ../STATUS.md
  - ../AGENT_MEMORY.md
---

# DEA Phase 6 Business Event Checkpoint

This checkpoint records the current MVP business-event impact surface after Phase 6 wiring.

Phase 4 built the backend posting services. Phase 6 connected business-event screens to those services through a preview -> saved draft -> permissioned confirm -> read-only result pattern.

## Event Impact Matrix

| Business event | UI confirm route | Financial impact | Commodity impact | Exposure impact | Rate-fixing impact | Payment impact |
|---|---|---|---|---|---|---|
| Fixed purchase | `/dea/business-events/fixed-purchase/<draft_id>/confirm/` | Yes: inventory/asset ledger and supplier payable/account rows. | Yes: fixed incoming movement to owned/vault account. | No. | No. | No. |
| Unfixed purchase | `/dea/business-events/unfixed-purchase/<draft_id>/confirm/` | No final monetary payable before fixing. | Yes: unfixed incoming movement. | Yes: open purchase exposure. | No. | No. |
| Purchase rate fixing | `/dea/business-events/purchase-rate-fixing/<draft_id>/confirm/` | Yes: supplier payable financial posting. | No physical movement. | Yes: allocation reduces/closes purchase exposure. | Yes: posted rate fixing and allocation. | No. |
| Fixed sale | `/dea/business-events/fixed-sale/<draft_id>/confirm/` | Yes: customer receivable/revenue posting. | Yes: fixed outgoing sale issue movement. | No. | No. | No. |
| Unfixed sale | `/dea/business-events/unfixed-sale/<draft_id>/confirm/` | No final monetary receivable/revenue before fixing. | Yes: unfixed outgoing sale issue movement. | Yes: open sale exposure. | No. | No. |
| Sale rate fixing | `/dea/business-events/sale-rate-fixing/<draft_id>/confirm/` | Yes: customer receivable/revenue posting. | No physical movement. | Yes: allocation reduces/closes sale exposure. | Yes: posted rate fixing and allocation. | No. |
| Customer receipt | `/dea/business-events/settlement/<draft_id>/confirm/` | Yes: cash/bank and customer receivable/advance posting. | No. | No. | No. | Yes: posted `PaymentVoucher`. |
| Supplier payment | `/dea/business-events/settlement/<draft_id>/confirm/` | Yes: supplier payable/advance and cash/bank posting. | No. | No. | No. | Yes: posted `PaymentVoucher`. |
| Karigar issue | `/dea/business-events/karigar/<draft_id>/confirm/` | No. | Yes: commodity movement from owned/vault to karigar custody. | No. | No. | No. |
| Karigar receipt | `/dea/business-events/karigar/<draft_id>/confirm/` | No. | Yes: commodity movement from karigar custody to owned/vault. | No. | No. | No. |

## Confirm Controls

- Preview POSTs remain side-effect free.
- Confirm routes are POST-only.
- Confirm routes are owner/admin/accountant gated.
- Member-role users are denied at confirm routes.
- Confirm services row-lock the saved `BusinessEventDraft`.
- Confirm services reject stale payload hashes and readiness blockers.
- Duplicate confirms return existing posted effects through service idempotency.
- Result pages show the posted voucher, journal/account/ledger rows where financial rows exist, commodity movements where commodity rows exist, exposure allocations where fixing exists, and payment vouchers where settlement exists.

## Verification On 2026-06-25

Passed:

- `manage.py test apps.tenant_apps.dea.tests.test_fixed_purchase_service --keepdb` with 5 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_unfixed_purchase_service --keepdb` with 5 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_rate_fixing_service --keepdb` with 10 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_fixed_sale_service --keepdb` with 5 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_unfixed_sale_service --keepdb` with 5 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_monetary_settlement_service --keepdb` with 6 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_karigar_service --keepdb` with 6 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 70 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 32 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 6 tests.
- `manage.py test apps.tenant_apps.dea.test_financial_reports --keepdb` with 8 tests.
- `manage.py test apps.tenant_apps.dea.tests.test_statement_boundary --keepdb` with 2 tests.
- `manage.py makemigrations dea rates --check --dry-run` with no model changes detected.

Inconclusive:

- A combined backend service run timed out after printing progress dots. The same suites passed when split into smaller focused commands. Continue using focused serial commands for checkpoint verification until tenant test database setup time is reduced.

## Remaining MVP Gaps Before Legacy Cleanup

- Taxes/GST are not modeled in commodity business-event flows.
- COGS and inventory costing are deferred.
- Product inventory lot creation/consumption is not integrated with DEA commodity movement.
- Karigar wastage, making charges, and finished-goods transformation are deferred.
- Payment allocation against specific invoices/fixings is basic/deferred.
- Metal-in-kind settlement is not implemented.
- Commodity sidecar reversal UI is not implemented.
- Broader tenant-isolation regression across all new DEA business-event routes should be added before production rollout.
- Export/print surfaces for business-event result pages are deferred.
- Old voucher/table-centric UI remains available and should not be removed until Phase 7 characterization and replacement checks pass.

## Next Recommended Step

Start Phase 7 with a cleanup readiness audit, not deletion. The first Phase 7 task should inventory legacy DEA routes and direct posting surfaces, mark which are still required by accountant workflows, and add characterization tests before any removal or route hiding.
