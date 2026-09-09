---
status: accepted
owner: project
updated: 2026-09-08
tags: [party, cache, redis, workspace]
---

# Stateless borrower autocomplete and optional Redis

The only supported heavy Select2 model widget is PartyAutocompleteWidget. Its
query and search fields are fixed, and its endpoint already enforces explicit
Workspace identity, membership, Party view permission, lifecycle, and RLS.
Caching a serialized widget/queryset unnecessarily couples loan forms to Redis
and requires shared state across workers.

Keep Select2's rendering, filtering, selected-option handling, and pagination,
but replace cached widget IDs with Django timestamp-signed endpoint URLs using
the dedicated `party.autocomplete.v1` salt. The endpoint validates the signature,
24-hour age, and exact request path, then reconstructs the fixed widget and active
Party queryset inside the current authorized Workspace context. No client-selected
model, query, filter definition, or permission is accepted. Tokens are not grants
of access; every request still passes normal authorization. No data is cached.

Workers need the same signing keys and reasonably synchronized clocks, but no
shared cache. Existing cached tokens stop working on rollout: reload an open
loan form to receive a new token. Expired forms also need a reload; retain entered
values before reloading. Normal POST borrower validation remains unchanged.

`CACHE_URL` explicitly configures the general Django cache. Its default is
`locmemcache://rokkad`, suitable for the remaining non-authoritative member-count
display cache. Redis can be selected explicitly. No correctness-critical or
cross-worker coordination state may be added to the default local-memory cache.
Future heavy widgets must either use an explicit stateless endpoint or introduce
a deliberately shared cache; do not assume arbitrary ModelSelect2 widgets inherit
Party's behavior. Redis client packages remain installed for the opt-in backend.

No schema migration or shared cache table is needed. The rejected alternative
was adding database cache storage and grants solely to transport a fixed widget.
