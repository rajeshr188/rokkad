---
status: complete
owner: project
updated: 2026-10-15
tags: [loans, party, export, release, production]
related: [../adr/2026-10-15-filtered-loan-excel-summary.md, reviewed-production-release-20261015.md]
---

# Loan summary export production release

The owner explicitly requests safe production deployment of the filtered Excel
export and Party balance breakdown. The scoped 20-file candidate excludes the
unrelated pending WhatsApp sender-onboarding notes. The owner separately approves
the existing encrypted production-data backup job to the configured R2 backup
bucket for the pre/post-release checks after automatic approval review requests
that explicit transfer scope. No provider setting, subscription date, customer
record or financial action is changed by this software deployment.

## Completed result

The coordinated switch completes on **15 October 2026, 14:19:08 IST**. Application source
`0dfd15cc7d0f8e8a2f66f30bf76490711712ce17` runs as `rokkad:loan-export-20261015-0dfd15cc7d0f` with image ID
`sha256:42d2c5221e0ed341d3ad4f8d42ffb809b1b091ec4a7c698645c24cbc302c1c70` in web, monitoring and the four scheduled application readers.
The source is pushed on `work/loan-servicing-contract-ld01`. All six groups pass in
[the exact-source CI run](https://github.com/rajeshr188/rokkad/actions/runs/38703900705); local affected selections and the four
directory JavaScript checks also pass. Group counts overlap and are not summed.

The first full Loans run finds one stale assertion among 2,487 cases: the new
export link preserves user-entered search text, while the test rejects that text
anywhere in an otherwise empty result fragment. The corrected test checks visible
results, absent cards, empty Excel rows and invalid foreign licence/series filters;
all existing cross-Workspace detail/document checks remain. Ten focused cases pass
before the exact corrected revision completes all six CI groups. Application and
financial code are identical between the first and corrected candidates.

The production-copy rehearsal restores 1,067,188 rows across
222 tables. All 219
original business-table projections stay exact, and financial source rows remain
exact after the bounded risk worker. The real read-only XLSX/Party checks cover
three Workspaces and 104 active-loan rows.
Amounts reconcile against canonical servicing balances. Individual filtered
exports take 2.767, 2.286, 0.646 seconds
under the restricted rehearsal reader. No workbook or raw customer row leaves
the private server.

No migration is pending or applied. The live switch pauses existing readers and
timers, captures a fresh private checkpoint, preserves all
219 original business projections,
checks read-only feature/closed/native/contract readers and refuses owner startup,
then installs the compatible image and separate verified static volume. Runtime
environment values, protected configuration, commands and mounts stay exact apart
from the reviewed image/static bindings. The predecessor image remains retained;
the schema-preserving recovery path restores those bindings without restoring or
overwriting customer rows.

Independent encrypted image download, local-key decryption, checksum verification
and exact image reload pass. The private key stays on the owner's computer and
temporary decrypted image files are removed. The first candidate's pre-release backup initially
refuses overlap with image preservation through its existing lock; a serialized
retry succeeds, and the resolved transient failure flag is cleared with logs kept.

## Production acceptance

Post-release read-only feature checks pass for 3 Workspaces,
104 active-loan rows and the three Party breakdowns.
The Loans list exports every filtered page; Party provides its active ordinary-loan
shortcut. Principal, interest, fees and total reconcile; completed age and unpaid
monthly charge coverage remain distinct. Unknown opening-period attribution
stays unavailable under the documented oldest-first reporting convention.

Both live readers match all 1870 committed runtime files, use
the restricted database role and effective UID 10001, and have no pending
migration or error line in their complete post-start logs. Public HTTPS checks
pass and all six existing timers are active. The post-release operational backup,
encrypted remote download verification and retention acceptance pass. The exact
disposable rehearsal database is removed; dumps, recovery images and private
proofs remain. JCL/JSK/Lakshmi grace remains through 22 October, 23:39:08 IST,
and WhatsApp activation remains disabled. Risk calculations and monitoring
policy are unchanged.
