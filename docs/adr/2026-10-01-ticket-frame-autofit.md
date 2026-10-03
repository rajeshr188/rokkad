---
status: accepted
owner: loans
updated: 2026-10-01
tags: [loans, tickets, pdf]
---

# Fit complete text across precision ticket frames

The owner reported recurring JCL overflow failures in different blocks and asked
for auto-sizing across the ticket. Previous changes enabled SHRINK only for
individual frames; fixed line spacing and character-count heuristics still limited
the renderer's ability to fit real content.

For schema-v4 SHRINK text frames, measure the whole formatted paragraph including
labels, explicit line breaks and padding. Keep the configured size when it fits.
Otherwise choose the largest fitting tenth-point size at or above 6 pt, scaling
explicit leading proportionately (automatic leading remains font size plus 2 pt).
Measure actual line widths as well as height. Do not truncate values or clip text.

SHRINK tables similarly choose a uniform fitting size, retain every cell/row and
check outer bounds plus text widths within padded cells. Fixed table padding is
retained. Images and QR codes keep their existing independent rendering rules.
If the minimum cannot fit, report the block and ask for a larger frame/layout.

New v4 starter and editor-added text/table frames default to SHRINK. Existing
WRAP/ERROR choices remain explicit; older schemas and Flow behavior keep their
previous rules. Publish a new audited JCL template revision setting every existing
text/table frame to SHRINK, without changing frame geometry, starting typography,
paper profiles, source facts or financial records.

Profile-render evidence identifies `layout-reportlab-profile-v4-fit2`. Previously
issued PDFs continue to reprint their stored bytes; published definitions are not
edited in place. There is no schema migration. Review fictional PDFs visually and
real ticket output only on the production host, without issuing documents during
verification. Physical printer calibration remains separate.
