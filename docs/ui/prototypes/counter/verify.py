"""Exercise the isolated prototype with the optional Playwright dependency."""
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright

output = Path(tempfile.gettempdir()) / 'rokkad-ux-prototype'
output.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width, height in [(1440, 1000), (390, 844)]:
        page = browser.new_page(viewport={'width': width, 'height': height}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(Path(__file__).with_name('index.html').as_uri())
        def capture(name):
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), name
            page.screenshot(path=str(output / f'{width}-{name}.png'), full_page=True)
        capture('borrower')
        page.locator('#search').fill('no matching person')
        assert page.get_by_text('No borrowers found.', exact=False).is_visible()
        page.locator('#search').fill('Lakshmi')
        page.locator('[data-person="0"]').click()
        page.get_by_role('button', name='Continue to collateral').click()
        page.get_by_role('button', name='Add another item').click()
        page.get_by_role('button', name='Remove item 2').click()
        page.locator('#weight-0').fill('0')
        page.get_by_role('button', name='Review terms').click()
        assert page.locator('#collateral-form').is_visible()
        page.locator('#weight-0').fill('8.50')
        page.locator('#photo').set_input_files({'name': 'sample.svg', 'mimeType': 'image/svg+xml', 'buffer': b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="8" fill="gold"/></svg>'})
        assert page.locator('#photo-preview img').is_visible()
        capture('collateral')
        page.get_by_role('button', name='Review terms').focus()
        page.get_by_role('button', name='Review terms').press('Enter')
        capture('review')
        page.get_by_role('button', name='Save sample draft').click()
        assert page.get_by_role('button', name='Approve sample loan').is_disabled()
        page.locator('#confirm-action').check()
        page.get_by_role('button', name='Approve sample loan').click()
        assert page.get_by_role('button', name='Confirm sample disbursal').is_disabled()
        page.locator('#confirm-action').check()
        page.get_by_role('button', name='Confirm sample disbursal').click()
        page.locator('#repayment-form input[type=checkbox]').check()
        page.get_by_role('button', name='Record sample repayment').click()
        assert page.locator('.summary-amount').inner_text() == '₹9,000'
        page.get_by_role('button', name='Use full balance').click()
        page.locator('#repayment-form input[type=checkbox]').check()
        page.get_by_role('button', name='Record sample repayment').click()
        capture('handoff')
        page.locator('#confirm-action').check()
        page.get_by_role('button', name='Confirm sample handoff').click()
        assert page.get_by_role('heading', name='Collateral handed back').is_visible()
        page.locator('#reset').click()
        page.get_by_role('button', name='Add borrower', exact=False).click()
        page.locator('#borrower-name').fill('Sample Person')
        page.locator('#borrower-phone').fill('9000000004')
        page.get_by_role('button', name='Add & select borrower').click()
        assert page.locator('[data-person="3"]').get_attribute('aria-pressed') == 'true'
        for view in ['loans', 'parties', 'rates', 'notify', 'setup', 'counter']:
            if width < 850:
                page.locator('#menu-toggle').click()
            page.locator(f'[data-view="{view}"]').click()
            assert page.locator('h1').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        page.close()
    browser.close()
print(f'PASS: desktop/mobile sample journeys, validation, navigation; screenshots: {output}')
