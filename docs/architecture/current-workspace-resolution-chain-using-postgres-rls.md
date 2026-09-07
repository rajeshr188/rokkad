Workspace resolution now has two connected but separate jobs:

1. Django decides which Workspace the request belongs to.
2. PostgreSQL RLS restricts database access to rows owned by that Workspace.

The middleware does not switch PostgreSQL schemas anymore. Every request stays in the shared `public` schema.

## End-to-end request flow

```text
Incoming HTTP request
        │
        ▼
Authentication middleware identifies request.user
        │
        ▼
SecureWorkspaceMiddleware
        │
        ├─ Public/exempt URL? ───────────────► Clear Workspace context
        │
        ▼
Resolve Workspace candidates
        │
        ├─ Domain mapping
        ├─ Workspace ID/slug in URL
        └─ User profile preference
        │
        ▼
Select candidate by priority
        │
        ▼
Validate domain/path agreement
        │
        ▼
Validate user membership + subscription
        │
        ▼
Enter workspace_context(workspace.id)
        │
        ├─ request.workspace = Workspace
        ├─ request.tenant = Workspace (temporary alias)
        └─ PostgreSQL app.workspace_id = Workspace ID
        │
        ▼
View/service executes ORM and SQL queries
        │
        ▼
PostgreSQL RLS filters rows by workspace_id
        │
        ▼
Response or exception
        │
        ▼
Middleware closes transaction and clears context
```

## 1. Middleware placement

The main implementation is [middleware_v2.py](C:\Users\rajes\OneDrive\Desktop\rokkad\apps\orgs\middleware_v2.py).

`SecureWorkspaceMiddleware` runs after:

- Session middleware
- Authentication middleware
- Message middleware

That ordering matters. By the time Workspace resolution begins, Django already knows:

```python
request.user
request.user.is_authenticated
```

It runs before most application-specific middleware and before the view.

## 2. Public and exempt requests

The following prefixes are explicitly public:

```python
EXEMPT_URLS = [
    "/accounts/",
    "/static/",
    "/media/",
    "/__debug__/",
]
```

For one of these requests, `_set_public_context()` does this:

```python
request.workspace = None
request.tenant = None
request.urlconf = settings.ROOT_URLCONF
```

It also closes any previously established Workspace context.

This explains why public code must tolerate an authenticated user with no Workspace. For example, a user can be authenticated while processing an account/signup or authentication page.

Public means “no business Workspace context.” It does not mean a synthetic public Workspace row must exist.

## 3. Candidate resolution

For a non-exempt request, the middleware collects up to three candidates.

### Domain candidate

The hostname is normalized:

```text
www.acme.example.com:8000
        ↓
acme.example.com
```

Then Django queries the global `Domain` model:

```python
Domain.objects.select_related("tenant").filter(
    domain=hostname
).first()
```

Despite the compatibility field name `tenant`, this points to the ordinary global `Company`/Workspace model. It does not represent a PostgreSQL schema.

Example:

```text
acme.example.com
    → Domain(domain="acme.example.com")
    → Company(id=12)
```

Domain resolution is the strongest candidate because a dedicated hostname is an authoritative routing statement.

### Path candidate

The middleware recognizes Workspace IDs in paths such as:

```text
/orgs/workspace/12/...
/orgs/company/12/...
/workspace/12/settings/...
```

It also recognizes Workspace slugs:

```text
/w/acme/...
```

For an ID path, it queries:

```python
Company.objects.filter(
    id=workspace_id,
    is_deleted=False,
).first()
```

For a slug path:

```python
Company.objects.filter(
    slug=workspace_slug,
    is_deleted=False,
).first()
```

`slug` is the dedicated immutable Workspace routing identifier.
`schema_name` remains non-routing legacy schema-tenancy metadata.

Conceptually:

```text
Company.slug == canonical Workspace route identifier
```

### Profile candidate

If the user is authenticated, the middleware can read:

```python
request.user.profile.workspace
```

This represents the user’s most recently selected Workspace.

It is a navigation preference and fallback. It is not, by itself, proof that the user is authorized. Membership is still checked later.

## 4. Resolution priority

The middleware selects candidates in this order:

1. Non-public domain Workspace
2. Non-public path Workspace
3. Non-public profile Workspace
4. Public domain marker
5. No Workspace

In simplified form:

```python
if domain_workspace:
    workspace = domain_workspace
elif path_workspace:
    workspace = path_workspace
elif profile_workspace:
    workspace = profile_workspace
else:
    workspace = None
```

The selected source is stored for diagnostics:

```python
request.tenant_resolution_source
```

Possible values include:

```text
domain
path
profile
domain-public
public
```

This is useful in logs and debugging because it tells you why a request acquired a particular Workspace.

## 5. Domain/path mismatch protection

Suppose the request hostname maps to Workspace A:

```text
a.example.com → Workspace 10
```

But the URL contains Workspace B:

```text
/w/workspace-b/...
```

The middleware detects:

```python
domain_workspace.id != path_workspace.id
```

For an ordinary user, it:

1. Logs the mismatch.
2. Clears Workspace context.
3. Shows an error.
4. Redirects to Workspace A’s dashboard.

This prevents a user from taking a URL from another Workspace and opening it under an authoritative tenant domain.

A platform administrator is permitted through this particular mismatch check, but RLS still needs an explicit effective Workspace context. Platform-admin status does not automatically disable database RLS.

## 6. Authentication behavior

### Unauthenticated request with a resolved Workspace

If the request resolves to a real Workspace but the user is not authenticated, the middleware clears the context and redirects to login:

```text
/accounts/login/?next=<original-path>
```

It does not expose Workspace business data to anonymous users.

### Unauthenticated request to a Workspace-required path

Paths such as these require Workspace context:

```text
/party/
/loans/
/rates/
/notify-v2/
/data-tools/
```

An unauthenticated request is redirected to login.

### Authenticated request without a Workspace

If a Workspace-required URL is requested but resolution produces no Workspace, the user is redirected to the Workspace selector.

This prevents `/loans/` from executing with an accidental or undefined ownership context.

## 7. Authorization after resolution

Resolution only answers:

> “Which Workspace is this request trying to use?”

It does not answer:

> “Is this user allowed to use it?”

The middleware next calls `_validate_workspace_access()`.

It checks:

1. Platform administrator status
2. Whether the Workspace is archived/deleted
3. Whether the user has a `Membership`
4. Subscription and entitlement state

The crucial membership query is conceptually:

```python
Membership.objects.get(
    user=request.user,
    company=workspace,
)
```

If it fails:

- access is denied;
- an audit record is written;
- an invalid profile selection is cleared;
- the user is redirected to the Workspace selector.

Therefore, changing `user.profile.workspace` does not grant access.

## 8. Establishing request context

After authorization succeeds, `_set_tenant_context()` runs:

```python
context_manager = workspace_context(workspace.id)
context_manager.__enter__()

request.workspace = workspace
request.tenant = workspace
```

`request.workspace` is canonical.

`request.tenant` exists only as a temporary compatibility alias for code written before the shared-schema migration. Both currently point to the same ordinary `Company` object.

No call resembling this remains:

```python
connection.set_tenant(...)
```

There is no schema switch.

## 9. What `workspace_context()` does

The implementation is in [context.py](C:\Users\rajes\OneDrive\Desktop\rokkad\apps\tenancy\context.py).

It first validates the Workspace ID:

```python
normalized_id = int(workspace_id)

if normalized_id <= 0:
    raise ImproperlyConfigured(...)
```

It then checks the application-level `ContextVar`:

```python
active_id = current_workspace_id()
```

Conflicting nesting is rejected:

```python
with workspace_context(10):
    with workspace_context(11):
        ...
```

That raises an error instead of silently switching ownership halfway through an operation.

Nesting with the same Workspace is allowed.

## 10. Transaction-local PostgreSQL context

`workspace_context()` opens a database transaction:

```python
with transaction.atomic():
```

It then sets:

```sql
SELECT set_config('app.workspace_id', '12', true);
```

The important parts are:

- `app.workspace_id` is a custom PostgreSQL setting.
- The value is the numeric Workspace primary key.
- `true` means transaction-local.

For Workspace 12, PostgreSQL effectively holds:

```text
app.workspace_id = 12
```

This setting exists only for that transaction. It is not intended to remain attached to the database connection after the transaction ends.

That prevents Workspace identity from leaking when Django or a connection pool reuses a PostgreSQL connection.

## 11. Application context and database context

There are two synchronized context values:

### Python context

```python
current_workspace_id()
```

This is backed by Python’s `ContextVar`.

It is used by model and service code.

### PostgreSQL context

```sql
current_setting('app.workspace_id', true)
```

This is used by RLS policies.

Both are set by the same `workspace_context()` operation.

This prevents code from having one Workspace in Python while PostgreSQL filters for another.

## 12. Direct row ownership

Every protected business model has a direct Workspace foreign key.

The shared base class is [models.py](C:\Users\rajes\OneDrive\Desktop\rokkad\apps\tenancy\models.py):

```python
class WorkspaceOwnedModel(models.Model):
    workspace = models.ForeignKey(
        "orgs.Company",
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
```

The ownership column is non-null.

Every Party, Loans, Notify v2, and Rates row therefore has:

```text
workspace_id = <Workspace primary key>
```

Even child/evidence tables have direct ownership. PostgreSQL does not need to join through a parent to determine which Workspace owns a child row.

## 13. Model write protection

`WorkspaceOwnedModel.save()` adds an application-level check.

### Workspace omitted

Inside Workspace 12:

```python
with workspace_context(12):
    Party.objects.create(display_name="Customer")
```

The base model assigns:

```text
party.workspace_id = 12
```

### Conflicting Workspace supplied

Inside Workspace 12:

```python
with workspace_context(12):
    Party.objects.create(
        workspace_id=13,
        display_name="Wrong Workspace",
    )
```

Django raises a validation error before saving.

### No context and no explicit owner

```python
Party.objects.create(display_name="Unowned")
```

This also fails.

However, model `save()` is not the ultimate security boundary because `bulk_create()`, queryset `update()`, raw SQL, and triggers can bypass it. PostgreSQL RLS remains the final boundary.

## 14. PostgreSQL RLS policy

Each of the 95 business tables has the same conceptual policy:

```sql
ALTER TABLE protected_table ENABLE ROW LEVEL SECURITY;
ALTER TABLE protected_table FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation
ON protected_table
USING (
    workspace_id =
    NULLIF(current_setting('app.workspace_id', true), '')::bigint
)
WITH CHECK (
    workspace_id =
    NULLIF(current_setting('app.workspace_id', true), '')::bigint
);
```

The migration operation is in [rls.py](C:\Users\rajes\OneDrive\Desktop\rokkad\apps\tenancy\rls.py).

### `USING`

`USING` controls which existing rows can be:

- selected;
- updated;
- deleted.

For Workspace 12, PostgreSQL behaves as though every query included:

```sql
WHERE workspace_id = 12
```

Even if application code forgets that filter.

### `WITH CHECK`

`WITH CHECK` controls the new row value produced by:

- inserts;
- updates.

Inside Workspace 12, PostgreSQL rejects a row with:

```text
workspace_id = 13
```

This protects bulk ORM and raw SQL operations too.

## 15. Missing context fails closed

When no context is set:

```sql
current_setting('app.workspace_id', true)
```

returns no useful Workspace ID.

The policy expression becomes effectively:

```text
workspace_id = NULL
```

That never evaluates to true.

Therefore:

```python
Party.objects.count()
PawnLoan.objects.count()
Rate.objects.count()
NotificationEvent.objects.count()
```

all return zero outside Workspace context when executed through the restricted runtime role.

This is why public pages can safely use the same database without seeing business rows.

## 16. Why the runtime role matters

RLS is only trustworthy if Django uses the restricted runtime login.

The normal application connection uses `rokkad_runtime`, which:

- is not a superuser;
- does not have `BYPASSRLS`;
- owns no protected tables;
- cannot create databases;
- cannot create roles.

The migration owner is separate and is used only through the migration settings module.

If the web process connected as the migration owner or a superuser, application queries could bypass RLS even though policies existed.

So isolation depends on all three:

```text
forced RLS policy
        +
transaction-local Workspace context
        +
restricted runtime database role
```

## 17. Query example

Assume the database contains:

```text
Party 101 → workspace_id 12
Party 102 → workspace_id 13
Party 103 → workspace_id 12
```

The view runs:

```python
Party.objects.all()
```

Under:

```python
with workspace_context(12):
```

PostgreSQL returns:

```text
Party 101
Party 103
```

It does not return Party 102.

The Django query did not need an explicit:

```python
.filter(workspace_id=12)
```

Selectors should still express appropriate domain filters, but tenant isolation does not depend on every developer remembering the Workspace condition.

## 18. Request cleanup

The middleware keeps the context manager on the request:

```python
request._workspace_context_manager
```

On a normal response:

```python
process_response()
```

closes it.

On an exception:

```python
process_exception()
```

closes it with exception information so the transaction rolls back.

Cleanup resets:

- the transaction-local PostgreSQL setting;
- the Python `ContextVar`;
- the active atomic transaction.

This is necessary because web-server processes and database connections serve many requests.

## 19. Profile preference after successful resolution

After access succeeds, the middleware may update:

```python
request.user.profile.workspace = workspace
```

This means the next generic Workspace-aware request can fall back to the last valid selection.

The profile is not the database security boundary. On every request, membership and subscription checks still run before context is established.

For selectors and views, [tenant_context.py](C:\Users\rajes\OneDrive\Desktop\rokkad\apps\orgs\tenant_context.py) makes the distinction explicit:

```python
resolve_request_workspace(request)
```

normally trusts only `request.workspace`.

Profile fallback requires an explicit opt-in:

```python
resolve_request_workspace(
    request,
    allow_profile_fallback=True,
)
```

That fallback is intended for non-authoritative user experience features, such as showing the last selected Workspace name.

## 20. Background tasks and commands

Workers do not pass through HTTP middleware. They must receive a Workspace ID explicitly:

```python
def process_batch(workspace_id, batch_id):
    with workspace_context(workspace_id):
        batch = NotificationBatch.objects.get(pk=batch_id)
        ...
```

Management commands follow the same rule:

```python
with workspace_context(workspace_id):
    seed_workspace_defaults()
```

A task should never infer its Workspace from:

- a schema name;
- a previous database connection state;
- a global variable;
- whichever Workspace the initiating user last selected.

The Workspace identity belongs in the task payload.

## 21. Control-plane versus business tables

Global control-plane tables are not tenant-filtered in the same way. Examples include:

- Workspace/Company
- Domain
- Membership
- invitations
- subscription ownership
- user profiles

These tables must remain queryable before a Workspace context is established because they are used to resolve and authorize that context.

Business tables are protected:

- Party
- Loans
- Notify v2
- Rates

This creates the boundary:

```text
Global control plane
    resolves and authorizes Workspace
                │
                ▼
Protected data plane
    operates under Workspace RLS
```

## 22. A concrete request example

For:

```text
GET /orgs/workspace/3/dashboard/
Host: localhost:8000
User: authenticated
```

the sequence is:

1. Domain lookup for `localhost` probably returns no Workspace.
2. The path regex extracts Workspace ID `3`.
3. Django loads active `Company(id=3)`.
4. Path resolution wins because there is no domain candidate.
5. Middleware verifies the user has Membership in Workspace 3.
6. Subscription checks run.
7. Middleware enters `workspace_context(3)`.
8. PostgreSQL receives transaction-local `app.workspace_id = 3`.
9. `request.workspace` becomes Company 3.
10. Dashboard selectors query Party, Loans, Notify v2, and Rates.
11. PostgreSQL permits only rows whose `workspace_id = 3`.
12. The response is produced.
13. Middleware closes the context and transaction.

That is the complete Workspace-resolution-to-RLS chain.
