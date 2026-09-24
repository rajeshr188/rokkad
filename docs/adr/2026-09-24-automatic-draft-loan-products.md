---
status: accepted
owner: project
updated: 2026-09-24
tags: [onboarding, workspace, loans, products]
related:
  - 2026-08-11-loans-product-obligation-and-risk-architecture.md
  - ../architecture/control-plane-contracts.md
---

# Automatic draft loan products on Workspace creation

The owner approved removing the manual standard-product seeding step. Customers
should choose the lending products they offer without first running an internal
bootstrap action.

Both ordinary and onboarding Workspace creation services prepare the four standard
product drafts after creating the Owner Membership, inside the same transaction.
The control plane invokes the existing Loans service under explicit
`workspace_context(new_workspace.pk)` and ordinary actor authorization. Failure
rolls back the Workspace, domain, Membership and product preparation together.
There is no model signal, schema provisioning, migration side effect or GET write.

Single-payment bullet, periodic-interest bullet, flexible partial-payment and EMI
products start as DRAFT. The owner or authorized setup administrator reviews and
enables selected versions. Preparation does not imply business acceptance of their
terms, availability, licensing, economic policy or numbering. Existing loans keep
their frozen product version. Product lifecycle and immutability rules are unchanged.

The idempotent `seed_default_loan_products --workspace-id ID` operator command stays
available for existing Workspace rollout and recovery, using restricted runtime
settings. It adds missing standard records without overwriting existing terms,
names or statuses; it never activates or reactivates a product. Run it explicitly
for each intended active Workspace when deploying to an existing installation.
Direct operator/import creation of Company rows does not invoke customer onboarding
and must continue to prepare its own required configuration.

The setup page says “Choose your lending products” and “Enable for new loans.”
The manual seed button is removed. Its old authorized POST endpoint is retained
for compatibility; the operator command is the documented recovery path.
