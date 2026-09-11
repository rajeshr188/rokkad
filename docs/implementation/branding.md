---
status: active
owner: project
updated: 2026-09-09
tags: [branding, ui]
---

# Rokkad branding

The owner approved the bilingual Rokkad / रोक्कड़ identity on 2026-09-09.
Use forest teal `#103f3a`, warm gold `#d5ab57`, and ivory `#faf8f2`.
Gold is decorative; teal supplies readable text and primary controls.

The later owner-approved monogram concept is saved as
`static/images/brand/rokkad-bilingual-monogram.png`: a gold upright stroke beside
a teal Hindi र, together suggesting an English R. This full logo is saved for
reuse; the current application still uses the earlier diamond-mark assets below.

The approved artwork is `static/images/brand/rokkad-hindi.png`. Its English
lettering uses a Devanagari-inspired headline, with the Hindi name below.
`rokkad-icon.png` is the generated square R-and-diamond companion for browser
tabs, touch bookmarks, and checkout. These are raster assets, not vector masters.

Include `components/brand.html` for the wordmark and `components/brand_head.html`
for browser icons and theme color. `static/css/brand.css` displays the original
wordmark through a bounded viewport, preserving the approved pixels while hiding
the surrounding presentation whitespace. Its percentages correspond to the
1774-by-887 source image; revisit them if the source changes. Header width is
176px on desktop and 154px on small screens. The Hindi name is included in alt text.

The shared shell covers public/auth pages, onboarding, account management, and
Workspace screens. The customer portal and Django admin also use the component.
Subscription invoice pages include it; billing emails use readable bilingual text
and teal styling so branding works without loading remote images. Checkout uses
the square icon. The README shows the approved artwork.

Workspace-uploaded logos and issued loan-document assets retain their own identity.
No published document revision or previously issued bytes are rewritten by this
branding change. Unreferenced historical image files remain for compatibility;
new product UI should use the assets in `images/brand/`.

See [Status](../STATUS.md) for validation and outstanding issues.
