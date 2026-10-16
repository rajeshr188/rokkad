"""Fictional counter-screen checks; all browser network requests are intercepted.

Run only the three test_review methods with Django test settings.
"""
import json
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from django.contrib.staticfiles import finders
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from playwright.sync_api import sync_playwright

from scripts.browser_fixtures import bootstrap_assets

from apps.tenant_apps.loans.tests import test_routine_entry as entries
from apps.tenant_apps.loans.tests import test_multi_item_paper as paper
from apps.tenant_apps.loans.tests import test_monitoring_presentation as native
from apps.tenant_apps.loans.tests import test_paper_entry_simplification as simple

OUT = Path('outputs/everyday-counter-20261016')
OUT.mkdir(parents=True, exist_ok=True)


def read(case, client, url, label, pages, records):
    start = time.perf_counter()
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)
    case.assertEqual(response.status_code, 200, (url, response.status_code))
    pages[label] = response.content.decode()
    (OUT / (label + '.html')).write_text(pages[label], encoding='utf-8')
    tables = Counter()
    for row in queries:
        tables.update(re.findall(r'FROM "([^"]+)"', row['sql']))
    records[label] = {'url': url, 'server_ms': round(1000 * (time.perf_counter() - start), 2),
                      'queries': len(queries), 'bytes': len(response.content),
                      'most_read_tables': tables.most_common(8)}
    return response


def browser(pages, records, prefix, responses=None):
    assets = {}
    for html in pages.values():
        for path in re.findall(r'["\'](/static/[^"\']+)', html):
            found = finders.find(path.removeprefix('/static/'))
            if found:
                assets[path] = Path(found)
    bootstrap = bootstrap_assets()
    with sync_playwright() as pw:
        chromium = pw.chromium.launch()
        for width in (1365, 390):
            context = chromium.new_context(viewport={'width': width, 'height': 900 if width > 600 else 844})
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('dialog', lambda dialog: dialog.accept())

            def respond(route):
                url = urlparse(route.request.url)
                name = url.path.rsplit('/', 1)[-1]
                if url.hostname == 'review.test' and name in pages:
                    route.fulfill(body=pages[name], content_type='text/html')
                elif responses and url.path in responses:
                    route.fulfill(body=responses[url.path], content_type='text/html')
                elif url.path in assets:
                    route.fulfill(path=str(assets[url.path]))
                elif name in bootstrap:
                    route.fulfill(path=str(bootstrap[name]), headers={'Access-Control-Allow-Origin': '*'})
                else:
                    route.abort()

            page.route('**/*', respond)
            for label in pages:
                errors.clear()
                page.goto('https://review.test/' + label)
                page.wait_for_timeout(150)
                record = page.evaluate('''() => ({
                    width: innerWidth, documentWidth: document.documentElement.scrollWidth,
                    height: document.documentElement.scrollHeight,
                    headings: [...document.querySelectorAll('h1,h2,h3')].filter(e => e.getClientRects().length).map(e => ({text:e.innerText,top:Math.round(e.getBoundingClientRect().top)})),
                    buttons: [...document.querySelectorAll('button,a.btn')].filter(e => e.getClientRects().length).map(e => ({text:e.innerText,top:Math.round(e.getBoundingClientRect().top),href:e.getAttribute('href')})),
                    fields: [...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(e => e.getClientRects().length).length,
                    detailLinks: [...document.querySelectorAll('a')].filter(e=>e.textContent.trim()==='Loans').map(e=>e.getAttribute('href')),
                    duplicateIds: [...new Set([...document.querySelectorAll('[id]')].map(e=>e.id).filter((id,i,a)=>a.indexOf(id)!==i))]
                })''')
                record['script_errors'] = errors[:]
                assert record['documentWidth'] <= width, (label, width, record['documentWidth'])
                assert not record['duplicateIds'], (label, record['duplicateIds'])
                assert not errors, (label, errors)
                records[label].setdefault('browser', {})[str(width)] = record
                page.screenshot(path=str(OUT / f'{label}-{width}.png'), full_page=True)
                if label in ('direct-entry','paper-entry','paper-default'):
                    description=page.locator('[name="collateral-0-description"]')
                    description.fill('Fictional unsaved counter edit')
                    blocked=page.evaluate('''() => {const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);return event.defaultPrevented;}''')
                    assert blocked, label
                    record['unsaved_guard_prevents_departure']=blocked
                if page.locator('[data-loan-tab]').count():
                    checks=[]
                    for section in ('overview','money','collateral','documents','history','followup'):
                        page.locator('[data-loan-tab="'+section+'"]').click()
                        assert page.locator('[data-loan-panel="'+section+'"]').is_visible()
                        checks.append(section)
                    record['tabs_exercised']=checks
            context.close()
        chromium.close()
    (OUT / (prefix + '-metrics.json')).write_text(json.dumps(records, indent=2), encoding='utf-8')


class CounterEntryLayouts(entries.RoutineEntryTests):
    get_test_schema_name = classmethod(lambda cls: 'everyday-entry-review')

    def test_review(self):
        client, path = self._entry_client()
        pages, records = {}, {}
        from apps.tenant_apps.rates.models import RateSource, Rate
        source=RateSource.objects.create(workspace=self.tenant, name='Fictional current quote', location='Local')
        Rate.objects.create(workspace=self.tenant, rate_source=source, buying_rate=3000, selling_rate=3100)
        read(self, client, path, 'direct-entry', pages, records)
        original = read(self, client, path + '?entry=paper', 'paper-entry', pages, records)
        self.configure(default_entry_purpose='PAPER')
        read(self, client, path, 'paper-default', pages, records)
        readiness=reverse('workspace_loans:pawn_valuation_readiness', args=[self.tenant.slug])
        readiness_response=client.get(readiness, {'series':self.series.pk, 'as_of':self.today,
            'metals':'GOLD', 'request_key':'1'})
        self.assertEqual(readiness_response.status_code, 200)
        original=client.get(path+'?entry=paper')
        response = client.post(path, self.paper_facts(original))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['review'], response.context['form'].errors)
        pages['paper-review'] = response.content.decode()
        records['paper-review'] = {'url': path, 'context': 'synthetic reviewed paper facts'}
        loan, _ = paper.MultiItemPaperTests.admit(self)
        listing = reverse('workspace_loans:pawn_loan_list', args=[self.tenant.slug])
        read(self, client, listing + '?borrower=' + str(loan.borrower_id), 'paper-list', pages, records)
        detail = read(self, client, reverse('workspace_loans:pawn_loan_detail', args=[self.tenant.slug, loan.pk]), 'paper-detail', pages, records)
        records['paper-detail']['primary_action'] = detail.context['primary_action']
        browser(pages, records, 'entry', {readiness:readiness_response.content.decode()})


class CounterNativeLayouts(native.MonitoringPresentationTests):
    get_test_schema_name = classmethod(lambda cls: 'everyday-native-review')

    def test_review(self):
        self.start_active_trial()
        self.amend(valuation_basis='CALCULATED_METAL_VALUE')
        client = self.make_workspace_client()
        client.force_login(self.actor)
        pages, records = {}, {}
        listing = reverse('workspace_loans:pawn_loan_list', args=[self.tenant.slug])
        read(self, client, listing + '?borrower=' + str(self.loan.borrower_id) + '&state=ACTIVE', 'native-list', pages, records)
        detail=read(self, client, reverse('workspace_loans:pawn_loan_detail', args=[self.tenant.slug, self.loan.pk]), 'native-detail', pages, records)
        from apps.tenant_apps.loans.selectors.loan_summary import get_loan_summary
        summary=get_loan_summary(self.loan,as_of_date=self.today)
        records['native-detail']['amount_comparison']={'recorded_total':str(detail.context['balance'].total_due),
            'collection_total':str(summary.balance.total_due),'collection_interest':str(summary.balance.interest_outstanding),
            'collection_basis':summary.balance_basis}
        dashboard = reverse('workspace_slug_dashboard', args=[self.tenant.slug])
        read(self, client, dashboard + '?section=full', 'dashboard-full', pages, records)
        for section in ('queues', 'overview'):
            read(self, client, dashboard + '?section=' + section, 'dashboard-' + section, {}, records)
        browser(pages, records, 'native')


class CounterPaperDisclosure(simple.PaperEntrySimplificationTests):
    get_test_schema_name = classmethod(lambda cls: 'everyday-paper-meaning-review')

    def test_review(self):
        loan, _, _ = self.admit()
        self.assertFalse(loan.transaction_reviews.exists())
        page=self.client.get(reverse('workspace_loans:pawn_loan_detail',args=[self.tenant.slug,loan.pk]))
        self.assertEqual(page.status_code,200)
        text=page.content.decode()
        evidence=page.context['evidence_quality']
        result={'loan_has_book_review':loan.transaction_reviews.exists(),
            'source_claim_confirmed_complete':page.context['recorded_history']['admission']['confirmed_complete'],
            'rendered_claim_checked':"paper activity was checked through" in text,
            'rendered_claim_required_for_auction':"Auction recovery requires complete transaction confirmation" in text,
            'transaction_coverage':evidence['transactions']['status'],
            'book_review_status':evidence['book_review']['status']}
        self.assertFalse(result['rendered_claim_checked'])
        self.assertFalse(result['rendered_claim_required_for_auction'])
        (OUT/'paper-meaning.json').write_text(json.dumps(result,indent=2))
