---
status: accepted
owner: project
updated: 2026-09-12
tags: [portability, party, identity, review]
---

# Reviewed Party source records with matching names

The owner authorized preparing the current jcl active set in a fresh test Workspace
and resolving matching names while preserving distinct source customer IDs. A name
alone does not establish that two source records should be merged. The ordinary
import remains conservative by default; this decision adds an explicit batch review
without changing Party identity or the canonical exchange schema.

An unfinished, validated party-master batch can record name decisions for selected
external IDs through the existing review page or `review_distinct_names`. The
command requires current import/create access, matching Workspace context and the
current preview digest. Each selected ID must identify exactly one source row.
The operator records a reason for keeping the records separate. This is a decision
about source records, not identity verification or proof of different physical people.

The batch mapping retains each selected external ID, its canonical source digest,
the exact IDs of currently matching destination names and the reason. At most 1000
source decisions and 1000 destination name matches per decision are supported.
Review runs ordinary validation again and writes an audit with actor, batch/source
fingerprint, IDs, reason and resulting approval. It creates no Party records.

The evaluator permits a name collision only for a matching decision. Intra-batch
name peers must both be reviewed; partial review leaves the collision unresolved.
Duplicate external IDs and phone/email/PAN/GST matches remain conflicts. Existing
source bindings still require unchanged source/local digests and never become a
request to create or merge another Party. For new source identities, the exact
destination name-match set must still equal the reviewed IDs; changes require
another review. The ordinary Workspace lock and commit reevaluation remain.

Each reviewed row carries an explicit warning. The normal preview hash covers the
decisions and row evidence; commit still requires the current digest, creation
access, warning acknowledgement and successful destination revalidation. Source
records create separate native Parties through the existing service. Source aliases
then preserve exact parent relationships for Loans and Party children. Nothing
rewrites display names or merges customers automatically.

Name decisions are batch-specific and cannot be saved in mapping presets. Replacing
the mapping removes them; applying a preset does not recreate them. There is no
global duplicate-name toggle, new model, migration, source-specific bypass or
change to financial import approval. See the
[Party operator flow](../flows/party-master-portability.md) and
[current legacy import plan](../plans/first-legacy-import.md).
