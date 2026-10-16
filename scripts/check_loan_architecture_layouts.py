"""Fictional Django/browser checks with every network request intercepted.

Run the two test_browser methods with django_project.settings.test.
"""
from pathlib import Path
import re
from urllib.parse import urlparse
from datetime import timedelta
from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.test import RequestFactory
from django.urls import reverse
from playwright.sync_api import sync_playwright

from scripts.browser_fixtures import bootstrap_assets

from apps.tenant_apps.loans.tests import test_monitoring_lifecycle as policies
from apps.tenant_apps.loans.tests import test_cohort_transaction_reviews as cohorts
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.web.paper_backlog import batch_review
from apps.tenant_apps.rates.models import Rate


def capture(case,pages):
    assets={}
    for html in pages.values():
        for name in re.findall(r'["\'](/static/[^"\']+)',html):
            found=finders.find(name.removeprefix('/static/'))
            if found:
                assets[name]=Path(found)
    bootstrap = bootstrap_assets()
    output=Path('outputs/loans-architecture-hardening-20261016')
    output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch()
        page=browser.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        def respond(route):
            url=urlparse(route.request.url)
            name=url.path.rsplit('/',1)[-1]
            if url.hostname=='architecture-layout.test' and name in pages:
                route.fulfill(body=pages[name],content_type='text/html')
            elif url.path in assets:
                route.fulfill(path=str(assets[url.path]))
            elif name in bootstrap:
                route.fulfill(path=str(bootstrap[name]),headers={'Access-Control-Allow-Origin':'*'})
            else:
                route.abort()
        page.route('**/*',respond)
        for width,height in ((1365,900),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            for name in pages:
                page.goto('https://architecture-layout.test/'+name)
                page.locator('#monitoring-policy').evaluate_all('rows => rows.forEach(row => row.open = true)')
                page.screenshot(path=str(output/f'{name}-{width}.png'),full_page=True)
                case.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
        case.assertEqual(errors,[])
        browser.close()


class PolicyLayouts(policies.MonitoringLifecycleTests):
    get_test_schema_name=classmethod(lambda cls:'loan-hardening-policy-layouts')

    def test_browser(self):
        self.policy=self.change(valuation_basis='CALCULATED_METAL_VALUE')
        Rate.objects.create(rate_source=self.source,buying_rate=3500,selling_rate=3600)
        future=self.change(effective_from=self.today+timedelta(days=5),valuation_basis='LOWER_OF_CALCULATED_AND_APPRAISAL')
        self.start_active_trial()
        client=self.make_workspace_client()
        client.force_login(self.actor)
        path=reverse('workspace_loans:pawn_economics_setup',args=[self.tenant.slug])
        page=client.get(path)
        form=page.context['monitoring_form']
        data={'action':'monitoring'}
        for name in form.fields:
            value=form[name].value()
            if name in {'replaces_scheduled','cancel_scheduled'}:
                continue
            data[form[name].html_name]='' if value is None else str(value)
        data.update({'monitoring-effective_from':self.today.isoformat(),'monitoring-replaces_scheduled':'on',
            'monitoring-amendment_reason':'Fictional review of the proposed evidence requirement'})
        reviewed=client.post(path,data)
        self.assertTrue(reviewed.context['monitoring_review_token'],reviewed.context['monitoring_form'].errors)
        self.assertEqual(reviewed.context['monitoring_review']['sample_loses_coverage'],1)
        cancelled=client.get(path,{'cancel_monitoring':future.pk})
        capture(self,{'policy-impact':reviewed.content.decode(),'policy-cancel':cancelled.content.decode()})


class CohortLayouts(cohorts.CohortReviewTests):
    def test_browser(self):
        with self.scoped(),patch('django.utils.timezone.localdate',return_value=self.day):
            self.opening(1)
            facts=self.facts()
            data=dict(selection='COHORT',series=self.series.pk,source_namespace=str(facts['source_namespace']),
                through_date=self.day.isoformat(),confirmed_complete='complete',source_reference='Fictional checked cutover and later records',
                future_capture='ROKKAD_ONLY',request_key=facts['request_key'],action='preview')
            request=RequestFactory().post('/',data)
            request.user,request.workspace=self.actor,self.a
            response=batch_review(request)
            self.assertEqual(response.status_code,200)
            self.assertFalse(m.LoanTransactionReview.objects.exists())
            capture(self,{'cohort-review':response.content.decode()})
