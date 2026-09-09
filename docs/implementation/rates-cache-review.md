---
status: active
owner: project
updated: 2026-09-08
tags: [rates, loans, cache, review]
related: [../STATUS.md]
---

# Rates and Redis dependency review

Rates remains a business dependency for calculated collateral valuation. The
Rates middleware cache was not the source used by Loans. The initial review
below describes the pre-cleanup behavior; its first recommendation is now implemented.

## Implemented cleanup

Removed the middleware registration and file, the post-save signal and app-ready
registration, and cached quote entries in the two legacy headers. No valuation,
RLS, rate data, or cache backend configuration changed. The obsolete cache-key
test was replaced by HTTP rate CRUD plus facade lookup coverage with default-cache
get/set/delete configured to raise ConnectionError. The subsequent autocomplete
change removes cached widget state entirely, so a shared cache is no longer
needed for borrower lookup. CACHE_URL now makes Redis optional; see
`cache-configuration.md` and the stateless-borrower-autocomplete ADR. The original
recommendations below are retained as review history.

## Actual Loans integration

`rates/facade.py:get_latest_commodity_valuation_rate` reads PostgreSQL through
the Workspace-owned Rate manager/RLS. It resolves Gold/Silver, defaults to INR
and 24k, and selects the latest quote at or before the requested date/time.
It does not access Django cache or request.grate/srate/brate.

- `loans/services/pawn_economics.py`: calculated/lower-of valuation for draft
  previews and saves, approval validation, splitting, and successor renewal
  economics. Rates supply buying prices; Loans' economic policies supply monthly
  interest and LTV limits. Appraisal-only draft economics skips the metal lookup.
- `loans/selectors/collateral_valuation.py`: current/as-of collateral value and
  LTV, combining quote, weight, purity, appraisal, custody, and exposure.
- `loans/selectors/release_readiness.py`: valuation evidence for collateral
  remaining after proposed releases, including renewal-related release checks.

The calculated value is buying price times net weight times purity percentage
divided by 100, with the workflow's rounding policy. Selling prices are not used
by these Loans callers. The per-metal dictionaries in economics/readiness are
local to one calculation, not Redis caches.

## Findings before cleanup

1. **Request availability:** enabled RateMiddleware performs three cache reads
   on authenticated Workspace requests even when the page does not display rates.
   Cache errors propagate. Base settings hard-code the default Redis cache.
2. **Write availability:** RatesConfig loads a post_save receiver which deletes
   cache keys and writes a Rate object. Cache errors propagate from this receiver
   too; removing only middleware would leave rate writes dependent on Redis.
3. **Incorrect cached quote identity:** cache keys distinguish Workspace and
   metal but omit purity/currency/source. Saving an older quote overwrites the
   cached object rather than resolving the latest quote. No post_delete
   invalidation exists. Writes are not deferred until transaction commit.
4. **Cold-path correctness/performance:** the middleware groups by metal only,
   then gets by metal/timestamp; same-time quotes of different purity/currency
   can produce MultipleObjectsReturned. Missing metals are not negatively
   cached, causing repeated database fallback when any metal is absent.
5. **Legacy consumers:** request.grate/srate/brate appear in the old tenant.html
   and _base.html headers. The current base_tenant.html extends layouts/workspace.html
   and does not use these values. Loans valuation is unaffected by these cache
   selection defects because it reads the facade directly.
6. **Other cache dependencies:** base settings also configure a Redis select2
   alias. PartyAutocompleteWidget extends ModelSelect2Widget and serves borrower
   selection. The workspace_member_count template tag also calls default cache.
   Removing Rates caching alone does not establish a Redis-free application.
7. **Separate product questions:** the facade has no quote-age cutoff or preferred
   source filter. Silver currently uses the same 24k purity choice as gold; the
   UI does not clearly specify a rate weight unit. These deserve explicit domain
   decisions, not silent changes during cache cleanup.

## Recommended sequence

Retire the middleware and its signal cache writer together after removing or
confirming retired header consumers; retain the Rates facade and RLS boundaries.
Add regression checks for loan valuation and rate creation with unavailable cache.
Keep market buying prices distinct from loan monthly-interest policies.

Then address cache configuration independently: make backend/location explicit,
and choose a shared non-Redis backend if running without Redis is required.
Do not assume per-process memory is sufficient for multi-worker Select2 tokens.
Verify borrower autocomplete across workers and remaining cache consumers before
claiming Redis is optional. No cache/settings migration is implemented here.

## Validation of the initial review

Read-only call-site/configuration review, plus isolated mocked cache outages:
both RateMiddleware.process_request and update_rate_cache propagate ConnectionError.
No database data was written and no Redis service was stopped. Test settings use
local-memory caches, so normal passing tests do not establish Redis-outage safety.

Cleanup validation: all 60 focused Rates, business-entrypoint, loan economics,
release-readiness, draft-service, and restricted-role HTTP operator checks pass,
including the explicit default-cache outage regression. `git diff --check` passes.
