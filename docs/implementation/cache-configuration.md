---
status: active
owner: project
updated: 2026-09-08
tags: [cache, redis, deployment]
---

# Cache configuration

Rokkad's default runtime no longer requires a Redis service. PostgreSQL remains
required. Set `CACHE_URL` in the deployment environment or local `.env`:

```dotenv
# Default: per-process, disposable display cache; no external service.
CACHE_URL=locmemcache://rokkad

# Optional: shared Redis cache (use your deployment's host/credentials).
# CACHE_URL=redis://127.0.0.1:6379/1
```

Restart web/worker processes after changing settings. No migration or Redis flush
is required. Explicitly selecting Redis requires that service to be reachable;
there is no silent fallback on connection failure. Redis Python dependencies
remain available for this option. Tests use a separate local-memory cache.

Rates reads PostgreSQL directly. Borrower autocomplete uses a signed, URL-bound
token and reconstructs its active-Party query for each authorized request. It
does not store tokens, querysets, or borrower data in any cache. Different workers
can serve the form and subsequent searches with the same signing keys, without
Redis or a shared filesystem. Current Workspace/Party access and RLS still apply.

After deploying this change, reload loan forms opened before the deployment.
Search tokens expire after 24 hours; retain unsaved values before reloading a
long-open form. Invalid, expired, or wrong-Workspace tokens return 404; denied
Party access remains 403. Ordinary borrower selection is revalidated on POST.

The remaining `workspace_member_count` helper caches display counts for five
minutes. Per-process caching is acceptable for that display, not for authorization,
billing, distributed locks, or financial state. Any future shared-state feature
must explicitly choose appropriate storage rather than relying on this default.
