"""Browser regression against actual Django detail responses and synthetic records.

Run with the test settings and an installed Playwright Chromium:
python manage.py test scripts.check_loan_detail_layouts.NativeLayouts.test_browser \
    scripts.check_loan_detail_layouts.ImportedLayouts.test_browser \
    --settings django_project.settings.test --keepdb --noinput
"""
import json
from pathlib import Path
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse
from playwright.sync_api import sync_playwright

from apps.orgs.models import Membership, Role
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.tests.test_pawn_draft_ui import PawnDraftUiTests
from apps.tenant_apps.loans.tests.test_imported_ticket_preview import ImportedTicketPreviewTests

OUTPUT = Path('outputs/loan-detail-mockups/implementation')
SECTIONS = ('overview', 'money', 'collateral', 'documents', 'history', 'followup')


def exercise_pages(pages):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    from urllib.request import urlopen
    bootstrap = {}
    for folder, name in (('css', 'bootstrap.min.css'), ('js', 'bootstrap.bundle.min.js')):
        url = f'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/{folder}/{name}'
        cached = OUTPUT.parent / name
        if not cached.exists():
            cached.write_bytes(urlopen(url, timeout=20).read())
        bootstrap[url] = cached
    # Resolve static assets before Playwright starts its synchronous event loop.
    assets = {}
    import re
    for html in pages.values():
        for path in re.findall(r'["\'](/static/[^"\']+)', html):
            found = finders.find(path.removeprefix('/static/'))
            if found:
                assets[path] = Path(found)
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 1000})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def respond(route):
            parsed = urlparse(route.request.url)
            if parsed.path in assets:
                route.fulfill(path=str(assets[parsed.path]))
            elif parsed.path.startswith('/fixture/'):
                route.fulfill(body=pages[parsed.path.split('/')[-1]], content_type='text/html')
            else:
                # No application endpoint is reachable; never submit a business action.
                route.fulfill(status=404, body='')

        def external(route):
            asset = bootstrap.get(route.request.url)
            if asset:
                route.fulfill(path=str(asset), headers={'Access-Control-Allow-Origin': '*'})
            else:
                route.abort()

        context.route('**/*', external)
        page.route('https://loan-layout.test/**', respond)
        for state in pages:
            page.goto('https://loan-layout.test/fixture/' + state)
            page.locator('[data-loan-layout="tabs"]').wait_for()
            assert page.locator('.loan-layout-nav').evaluate('(e)=>getComputedStyle(e).display') == 'flex', 'Bootstrap must load'
            root = page.locator('[data-loan-detail]')
            page.evaluate('''() => {
                const root = document.querySelector('[data-loan-detail]');
                window.originalControls = [...root.querySelectorAll('form, input, select, textarea, a, img, dialog')];
                window.originalForms = [...root.querySelectorAll('form')].map(f => [f, f.action, f.method, new FormData(f).get('csrfmiddlewaretoken')]);
                window.originalBlocks = [...root.querySelectorAll('[data-loan-block]')];
            }''')
            files = root.locator('input[type=file]')
            if files.count():
                files.first.set_input_files({'name': 'kept-photo.jpg', 'mimeType': 'image/jpeg', 'buffer': b'synthetic photo selection'})
            for layout in ('tabs', 'desk', 'sections', 'classic', 'sections', 'desk', 'tabs', 'classic'):
                page.locator('#loan-detail-layout').select_option(layout)
                assert root.get_attribute('data-loan-layout') == layout
                assert root.locator('.loan-more-actions > summary').is_visible()
                root.locator('.loan-more-actions').evaluate('(e)=>e.open=true')
                assert root.locator('.loan-more-actions a').first.is_visible()
                root.locator('.loan-more-actions').evaluate('(e)=>e.open=false')
                assert page.evaluate('''() => {
                    const root = document.querySelector('[data-loan-detail]');
                    return originalControls.every(e => root.contains(e)) && originalBlocks.every(e => root.contains(e)) &&
                      originalForms.every(([f,a,m,c]) => f.action===a && f.method===m && new FormData(f).get('csrfmiddlewaretoken')===c);
                }'''), (state, layout, 'lost or changed controls')
                ids = root.locator('[id]').evaluate_all('(nodes) => nodes.map(n=>n.id)')
                assert len(ids) == len(set(ids)), (state, layout, 'duplicate IDs')
                if files.count():
                    assert files.first.evaluate('(e)=>e.files[0].name') == 'kept-photo.jpg'
                if layout != 'classic':
                    for section in SECTIONS:
                        if layout == 'sections':
                            page.locator('#loan-section-' + section).click()
                            fold = page.locator('#loan-panel-' + section).locator('..')
                            if fold.get_attribute('open') is None:
                                page.locator('#loan-section-' + section).click()
                        else:
                            page.locator('#loan-tab-' + section).click()
                        assert page.locator('#loan-panel-' + section).is_visible()
                        checks.append([state, layout, section])
                # Original hashes activate the right group and unfold its ancestors.
                page.evaluate("location.hash='business-events'")
                page.locator('#business-events').wait_for(state='visible')
                assert page.locator('#business-events').is_visible()
                page.evaluate("location.hash='collateral-gallery'")
                page.locator('#collateral-gallery').wait_for(state='visible')
            # All originals are in the original parent/location when Classic is selected.
            assert page.evaluate('''() => originalBlocks.every(e => e.previousSibling.nodeType === Node.COMMENT_NODE)''')
            page.locator('#loan-detail-layout').select_option('tabs')
            page.locator('#loan-tab-overview').focus()
            page.keyboard.press('ArrowRight')
            assert page.locator('#loan-tab-money').get_attribute('aria-selected') == 'true'
            page.keyboard.press('End')
            assert page.locator('#loan-tab-followup').get_attribute('aria-selected') == 'true'
            page.keyboard.press('Home')
            assert page.locator('#loan-tab-overview').get_attribute('aria-selected') == 'true'
            for width in (1280, 736, 390, 320):
                page.set_viewport_size({'width': width, 'height': 1000})
                for layout in ('tabs', 'desk', 'sections'):
                    page.locator('#loan-detail-layout').select_option(layout)
                    for section in SECTIONS:
                        if layout == 'sections':
                            page.locator('#loan-panel-' + section).locator('..').evaluate('(e)=>e.open=true')
                        else:
                            page.locator('#loan-tab-' + section).click()
                        size = root.evaluate('(e)=>[e.clientWidth,e.scrollWidth]')
                        if size[1] > size[0] + 1:
                            print(json.dumps(root.evaluate('''root => [...root.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>root.getBoundingClientRect().right+1 && e.getBoundingClientRect().width).map(e=>[e.tagName,e.className,e.textContent.slice(0,90)])''')))
                            page.screenshot(path=str(OUTPUT / f'overflow-{state}.png'), full_page=True)
                        assert size[1] <= size[0] + 1, (state, layout, section, width, size)
                    if state in ('active', 'imported') and width in (1280, 390):
                        if layout != 'sections':
                            page.locator('#loan-tab-overview').click()
                        page.screenshot(path=str(OUTPUT / f'{state}-{layout}-{width}.png'), full_page=True)
            page.set_viewport_size({'width': 1280, 'height': 1000})
            page.locator('#loan-detail-layout').select_option('desk')
            page.reload()
            assert root.get_attribute('data-loan-layout') == 'desk'
            # Duplicate/HTMX initialization must not duplicate listeners or shells.
            page.evaluate('window.rokkadLoanLayouts.init(document)')
            assert root.locator('.loan-layout-shell').count() == 1
            key = root.get_attribute('data-layout-key')
            page.evaluate('(key)=>localStorage.removeItem(key)', key)
            page.goto('https://loan-layout.test/fixture/' + state + '#business-events')
            assert page.locator('#loan-panel-history').is_visible()
            # Separate user/workspace preference key is never read as this user's choice.
            page.evaluate("localStorage.setItem('rokkad.loanDetailLayout.v1:other-user:other-workspace','classic')")
            page.reload()
            assert root.get_attribute('data-loan-layout') == 'tabs'
            page.evaluate('(key)=>localStorage.setItem(key,"obsolete-layout")', key)
            page.reload()
            assert root.get_attribute('data-loan-layout') == 'tabs'
            page.evaluate('(key)=>localStorage.removeItem(key)', key)
        assert not errors, errors
        # Storage failure still permits every layout for this visit.
        blocked = browser.new_context()
        blocked.route('**/*', external)
        blocked.add_init_script("Storage.prototype.getItem=Storage.prototype.setItem=function(){throw new Error('blocked storage')}")
        other = blocked.new_page()
        other.route('https://loan-layout.test/**', respond)
        other.goto('https://loan-layout.test/fixture/' + next(iter(pages)))
        other.locator('#loan-detail-layout').select_option('classic')
        assert 'unavailable' in other.locator('[data-layout-message]').inner_text()
        # Without JS the complete server-rendered Classic remains accessible.
        nojs = browser.new_context(java_script_enabled=False)
        nojs.route('**/*', external)
        other = nojs.new_page()
        other.route('https://loan-layout.test/**', respond)
        other.goto('https://loan-layout.test/fixture/' + next(iter(pages)))
        assert other.locator('[data-loan-detail]').get_attribute('data-loan-layout') == 'classic'
        assert not other.locator('[data-loan-layout-controls]').is_visible()
        assert other.locator('[data-loan-block="header"]').is_visible()
        browser.close()
    (OUTPUT / ('checks-' + next(iter(pages)) + '.json')).write_text(json.dumps({'state': 'PASS', 'sections_checked': checks}, indent=2))


class NativeLayouts(PawnDraftUiTests):
    def test_browser(self):
        license, series = self._configured_setup()
        self.client.post(reverse('loans:pawn_loan_create'), self._payload(license, series))
        loan = PawnLoan.objects.get()
        url = reverse('loans:pawn_loan_detail', args=[loan.pk])
        pages = {}

        def capture(label):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            pages[label] = response.content.decode()

        capture('draft')
        license.is_active = False
        license.save(update_fields=['is_active'])
        capture('blocked')
        license.is_active = True
        license.save(update_fields=['is_active'])
        self.client.post(reverse('loans:pawn_loan_approve', args=[loan.pk]))
        capture('approved')
        self.client.post(reverse('loans:pawn_loan_disburse', args=[loan.pk]), {'effective_date': '2026-07-18'})
        capture('active')
        viewer = get_user_model().objects.create_user(username='layout-viewer')
        role, _ = Role.objects.get_or_create(name='Viewer')
        Membership.objects.create(user=viewer, company=self.tenant, role=role)
        self.client.force_login(viewer)
        capture('viewer')
        self.client.force_login(self.owner)
        PawnLoan.objects.filter(pk=loan.pk).update(state='CLOSED')
        capture('closed')
        exercise_pages(pages)


class ImportedLayouts(ImportedTicketPreviewTests):
    def test_browser(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from apps.tenancy.testing import WorkspaceTestCase
        WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        client = Client()
        client.force_login(self.actor)
        with patch('django.templatetags.static.StaticNode.handle_simple', side_effect=lambda path: '/static/' + path):
            response = client.get(reverse('workspace_loans:pawn_loan_detail', args=[self.a.slug, self.loan.pk]))
        self.assertContains(response, 'Print imported loan copy')
        exercise_pages({'imported': response.content.decode()})
