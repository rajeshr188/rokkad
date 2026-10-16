---
status: archived
owner: project
updated: 2026-10-17
tags: [reference, documents, provenance]
---

# Original reference documents and historical PDF samples

These six assets were relocated during FW-024; none was discarded or regenerated.
The [manifest](manifest.json) records original/destination paths, sizes, SHA-256
hashes and the source commit. All destination bytes match their originals.

- [Original template pack](template-pack/template_pack.zip), formerly root
  `template_pack.zip`: eight reference DOCX/PDF files (Condition1, D31, dup, org).
  This ZIP is original reference material, not a runtime template or build input.
- [Form E landscape sample](pdf-previews/form-e-a4-landscape-sample.pdf).
- [Form E facing preview](pdf-previews/form-e-facing_a4-preview.pdf).
- [Form E landscape preview](pdf-previews/form-e-landscape_a4-preview.pdf).
- [Khata integration sample](pdf-previews/khata-integration-sample.pdf).
- [Khata label sample](pdf-previews/khata-label-sample.pdf).

PDFs were formerly under `output/pdf/`. They are retained as dated design/evidence
references; they do not certify current generated output or physical printer
acceptance. New generated previews belong under ignored `outputs/<dated-task>/`.
Historical backticked paths remain understandable through the manifest.
