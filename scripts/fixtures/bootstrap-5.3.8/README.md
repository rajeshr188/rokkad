# Bootstrap browser fixtures

These two unmodified Bootstrap 5.3.8 distribution assets are test inputs, retained
under the adjacent MIT license. They are excluded from the production Docker
source allowlist. Source URLs and SHA-256/SHA-384 hashes are in [manifest.json](manifest.json).
The copies came from the existing layout cache; SHA-384 values match the SRI pins
in `templates/layouts/base.html`.

`python scripts/browser_fixtures.py` verifies both files. All five layout scripts
load them through `scripts.browser_fixtures`; no download or pre-existing outputs
directory is needed. Browser requests remain intercepted by each layout script.

When deliberately upgrading, update the versioned fixture directory, manifest,
helper and source-template pins together after checking the upstream license and
distribution hashes. Re-run affected layouts. Do not regenerate a manifest merely
to accept unexpectedly modified bytes.
