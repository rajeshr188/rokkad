---
status: archived
owner: project
updated: 2026-10-17
tags: [context, preservation, repository]
---

# Context before FW-024 cleanup

All five source documents are retained in full. The
[manifest](snapshot-manifest.json) records source commit, original bytes/hash,
original link base, original-copy path and browsable-copy hash.

| Original | Reading copy | Exact original bytes |
|---|---|---|
| Agent memory | [Memory](AGENT_MEMORY.md) | [Original](AGENT_MEMORY.md.source.txt) |
| Status | [Status](STATUS.md) | [Original](STATUS.md.source.txt) |
| Active plan | [Plan](plans/active.md) | [Original](plans/active.md.source.txt) |
| Root README | [README](README.md) | [Original](README.md.source.txt) |
| Contributor guide | [Contributing](CONTRIBUTING.md) | [Original](CONTRIBUTING.md.source.txt) |

Reading copies mark archived status, add a notice, rebase links and normalize whitespace. Literal
paths and dated claims remain historical evidence, including already obsolete
references. Exact originals allow byte-for-byte comparison without Git recovery.
Do not execute old next steps as current instructions. Start with
[current Status](../../../STATUS.md) and [current memory](../../../AGENT_MEMORY.md).
The [reference-asset manifest](../../reference/manifest.json) maps moved binary
documents. No ADR, contract, implementation report or historical migration is
removed by this context compaction.
