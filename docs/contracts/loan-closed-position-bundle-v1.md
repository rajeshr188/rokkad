---
status: active
owner: loans
updated: 2026-10-09
tags: [loans, contract, portability, media]
---

# loan-closed-position-bundle/1

This ZIP carries one [loan-closed-position/1](loan-closed-position-v1.md)
document and its retained source attachments. It does not carry a reconstructed
financial timeline, operational agreement, Party master, Workspace setup or
source-local database identifiers for restoration. Existing published history,
opening and servicing bundle profiles are unchanged.

The exact entries are position.json, manifest.json and media/<sha256> for each
distinct file checksum. No extra paths, directories or duplicate ZIP names are
accepted. The total uploaded and expanded size is at most 32 MiB; at most 100
attachment claims are accepted. position.json retains its own 2 MiB bound.

manifest.json has exactly these keys:

| Key | Meaning |
| --- | --- |
| profile | loan-closed-position-bundle/1 |
| position_sha256 | SHA-256 of the canonical position document using the existing history-contract digest |
| earlier_history | UNAVAILABLE |
| financial_actions | Empty array; this profile contains no financial replay |
| media | Attachment claims, with exactly sha256, size, name, mime_type and source_evidence |

Each sha256 is a 64-character lower-case hexadecimal SHA-256 of the exact file
bytes. size is a positive integer and must match those bytes. name is a nonempty
filename of at most 255 characters, without control characters. mime_type is one
of image/jpeg, image/png, image/webp, application/pdf or application/octet-stream,
matching existing portable historical-attachment support. source_evidence is the
preserved JSON object; its verified_source_file.sha256 must match the file checksum.
Multiple source claims may reference identical bytes without duplicating the ZIP
file. Media requires a non-null retained_evidence document.

Export validates stored source/media bindings and bytes. Missing or corrupt files
are errors. Restore requires current owner authority, exact imported Party source
mapping and an existing scoped series, followed by signed preview/confirmation
through the ordinary closed-position admission service. Destination IDs are new;
source number, document, known original facts and unavailable-history declaration
remain unchanged. A repeated identical reviewed submission returns the existing
loan and does not append duplicate media. File/document/source changes require
a new review; a conflicting accepted origin is never overwritten.

Implementation and tests are documented in [IP-03](../implementation/loan-position-import-ip03.md).
