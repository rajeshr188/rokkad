from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse

from apps.orgs.models import Company, Domain, Membership, Role
from apps.subscriptions.models import Plan, Subscription
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnLoan, LoanNumberSequence
from apps.tenant_apps.loans.services import create_pawn_loan_economic_policy, create_pawn_metal_interest_rate_policy
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.party.models import Party


@override_settings(
    ALLOWED_HOSTS=["testserver", "phase11-a.test", "phase11-b.test"],
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class LoansWorkspaceRouteContractTests(TestCase):
    def setUp(self):
        clock = patch("django.utils.timezone.localdate", return_value=date(2026, 9, 10))
        clock.start()
        self.addCleanup(clock.stop)
        self.user = get_user_model().objects.create_user(
            username="phase10-loans-owner", password="test"
        )
        self.role, _ = Role.objects.get_or_create(name="Owner")
        self.plan = Plan.objects.create(
            name="Phase 10 trial",
            tier=Plan.PlanTierChoices.STARTER,
            price=0,
            description="Route contract trial",
        )
        self.workspace_a = self._workspace("workspace-a", "legacy_schema_a")
        self.workspace_b = self._workspace("workspace-b", "legacy_schema_b")
        Domain.objects.create(
            tenant=self.workspace_a, domain="phase11-a.test", is_primary=True
        )
        Domain.objects.create(
            tenant=self.workspace_b, domain="phase11-b.test", is_primary=True
        )
        self.loan_a = self._loan(self.workspace_a, "P10-A")
        self.loan_b = self._loan(self.workspace_b, "P10-B")
        self.client = Client()
        self.client.force_login(self.user)

    def _workspace(self, slug, schema_name):
        workspace = Company.objects.create(
            schema_name=schema_name,
            slug=slug,
            name=slug,
            owner=self.user,
            creator=self.user,
        )
        Membership.objects.create(
            user=self.user, company=workspace, role=self.role
        )
        Subscription.objects.create(company=workspace, plan=self.plan)
        return workspace

    def _loan(self, workspace, number):
        with workspace_context(workspace.pk):
            party = Party.objects.create(display_name=f"Borrower {number}")
            license = LoanLicense.objects.create(
                workspace=workspace,
                name=f"License {number}",
                license_number=number,
                issued_on=date(2026, 1, 1),
                expires_on=date(2027, 1, 1),
            )
            series = LoanSeries.objects.create(
                license=license, code=number[-1], name=number
            )
            return PawnLoan.objects.create(
                workspace=workspace,
                product_version=ensure_test_product_version(workspace),
                license=license,
                series=series,
                borrower=party,
                loan_number=number,
                principal_amount=Decimal("1000.00"),
                monthly_interest_rate=Decimal("2.000000"),
                loan_date=date(2026, 8, 17),
                created_by=self.user,
            )

    def _detail_url(self, workspace, loan):
        return f"/w/{workspace.slug}/loans/internal/{loan.pk}/"

    def test_explicit_path_controls_workspace_and_rls_visibility(self):
        response = self.client.get(self._detail_url(self.workspace_a, self.loan_a))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.workspace, self.workspace_a)
        self.assertContains(response, "P10-A")

    def test_named_workspace_loan_aliases_precede_the_deep_route_dispatcher(self):
        match = resolve(f"/w/{self.workspace_a.slug}/loans/list/")

        self.assertEqual(match.url_name, "workspace_slug_loan_list")

    def _complete_numbering(self):
        with workspace_context(self.workspace_a.pk):
            LoanNumberSequence.objects.create(
                series=self.loan_a.series, document_kind="PAWN_LOAN",
                prefix="SETUP-", width=5, maximum_number=10000,
            )

    def test_missing_numbering_is_offered_before_economics(self):
        response = self.client.get(reverse("workspace_slug_loan_create", kwargs={
            "workspace_slug": self.workspace_a.slug,
        }))
        license_url = f"/w/{self.workspace_a.slug}/loans/setup/licenses/{self.loan_a.license_id}/"
        self.assertContains(response, f'href="{license_url}"')
        self.assertContains(response, "Set up a series")
        with workspace_context(self.workspace_a.pk):
            self.assertFalse(LoanNumberSequence.objects.filter(series=self.loan_a.series).exists())

    def test_create_setup_link_keeps_workspace_on_global_host(self):
        self._complete_numbering()
        self.user.profile.workspace = self.workspace_b
        self.user.profile.save(update_fields=["workspace"])
        response = self.client.get(reverse(
            "workspace_slug_loan_create",
            kwargs={"workspace_slug": self.workspace_a.slug},
        ))
        setup_url = f"/w/{self.workspace_a.slug}/loans/setup/economics/"
        self.assertContains(response, f'href="{setup_url}"')
        setup = self.client.get(setup_url)
        self.assertEqual(setup.status_code, 200)
        self.assertEqual(setup.wsgi_request.workspace, self.workspace_a)
        self.assertNotContains(setup, 'href="/loans/')
        self.assertContains(setup, 'aria-label="PawnLoan setup"')
        self.assertContains(setup, f'/w/{self.workspace_a.slug}/loans/setup/products/')

    def test_named_loan_pages_keep_local_navigation_scoped(self):
        for name, extra in [
            ("workspace_slug_loan_list", {}),
            ("workspace_slug_loan_detail", {"pk": self.loan_a.pk}),
            ("workspace_slug_settings_numbering", {}),
        ]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name, kwargs={
                    "workspace_slug": self.workspace_a.slug, **extra,
                }))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'href="/loans/')
                self.assertNotContains(response, 'action="/loans/')
                if name == "workspace_slug_loan_list":
                    self.assertContains(response, "data-loan-setup-link")

    def test_missing_borrower_action_keeps_workspace(self):
        self._complete_numbering()
        with workspace_context(self.workspace_a.pk):
            create_pawn_loan_economic_policy(
                workspace=self.workspace_a, license=self.loan_a.license,
                valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal("0.8"),
                advance_interest_periods=1, effective_from=date(2026, 1, 1), actor=self.user,
            )
            for metal, rate in (("GOLD", "2"), ("SILVER", "4")):
                create_pawn_metal_interest_rate_policy(
                    workspace=self.workspace_a, license=self.loan_a.license, metal=metal,
                    monthly_interest_rate=Decimal(rate), effective_from=date(2026, 1, 1), actor=self.user,
                )
        with workspace_context(self.workspace_a.pk):
            Party.objects.filter(workspace=self.workspace_a).update(
                status=Party.PartyStatus.INACTIVE,
            )
        response = self.client.get(reverse("workspace_slug_loan_create", kwargs={
            "workspace_slug": self.workspace_a.slug,
        }))
        party_url = reverse("workspace_party:party_create", kwargs={
            "workspace_slug": self.workspace_a.slug,
        })
        self.assertContains(response, f'href="{party_url}"')
        self.assertEqual(self.client.get(party_url).status_code, 200)

    def test_loan_section_redirects_keep_workspace_and_fragment(self):
        for section, fragment in [
            ("items", "#collateral"),
            ("payments", "#financial-events"),
            ("transactions", "#financial-events"),
            ("statement", ""),
        ]:
            with self.subTest(section=section):
                kwargs = {"workspace_slug": self.workspace_a.slug, "pk": self.loan_a.pk}
                response = self.client.get(reverse(
                    f"workspace_slug_loan_detail_{section}", kwargs=kwargs,
                ))
                self.assertRedirects(response, reverse(
                    "workspace_slug_loan_detail", kwargs=kwargs,
                ) + fragment)

    def test_wrong_workspace_cannot_read_known_loan_id(self):
        response = self.client.get(self._detail_url(self.workspace_b, self.loan_a))

        self.assertEqual(response.status_code, 404)

    def test_unknown_slug_fails_closed(self):
        response = self.client.get(
            f"/w/unknown-workspace/loans/internal/{self.loan_a.pk}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_matching_domain_and_slug_resolve_the_same_workspace(self):
        response = self.client.get(
            self._detail_url(self.workspace_a, self.loan_a),
            HTTP_HOST="phase11-a.test",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.workspace, self.workspace_a)

    def test_conflicting_domain_and_slug_fail_closed(self):
        response = self.client.get(
            self._detail_url(self.workspace_b, self.loan_b),
            HTTP_HOST="phase11-a.test",
        )

        self.assertEqual(response.status_code, 403)

    def test_schema_name_is_not_accepted_as_route_identity(self):
        response = self.client.get(
            f"/w/{self.workspace_a.schema_name}/loans/internal/{self.loan_a.pk}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_workspace_slug_is_immutable(self):
        self.workspace_a.slug = "renamed-workspace"

        with self.assertRaisesRegex(ValidationError, "immutable"):
            self.workspace_a.save()

    def test_profile_preference_cannot_override_explicit_path(self):
        self.user.profile.workspace = self.workspace_b
        self.user.profile.save(update_fields=["workspace"])

        response = self.client.get(self._detail_url(self.workspace_a, self.loan_a))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.workspace, self.workspace_a)

    def test_removed_membership_denies_explicit_workspace_path(self):
        Membership.objects.filter(
            user=self.user, company=self.workspace_a
        ).delete()

        response = self.client.get(self._detail_url(self.workspace_a, self.loan_a))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/orgs/workspace/")

    def test_subscription_contract_allows_and_denies_without_bypass(self):
        allowed = self.client.get(self._detail_url(self.workspace_a, self.loan_a))
        self.assertEqual(allowed.status_code, 200)

        self.workspace_a.subscription.delete()
        denied = self.client.get(self._detail_url(self.workspace_a, self.loan_a))
        self.assertEqual(denied.status_code, 302)
        self.assertIn("/settings/billing/plans/", denied.url)

    def test_two_workspace_paths_remain_independent(self):
        response_a = self.client.get(self._detail_url(self.workspace_a, self.loan_a))
        response_b = self.client.get(self._detail_url(self.workspace_b, self.loan_b))

        self.assertContains(response_a, "P10-A")
        self.assertNotContains(response_a, "P10-B")
        self.assertContains(response_b, "P10-B")
        self.assertNotContains(response_b, "P10-A")

    def test_legacy_route_does_not_use_profile_preference_as_authority(self):
        self.user.profile.workspace = self.workspace_a
        self.user.profile.save(update_fields=["workspace"])

        response = self.client.get(f"/loans/internal/{self.loan_a.pk}/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/orgs/workspace/")


    def test_collateral_scan_redirects_and_old_qr_paths_keep_workspace(self):
        from apps.tenant_apps.loans.models import PawnCollateralItem
        with workspace_context(self.workspace_a.pk):
            item = PawnCollateralItem.objects.create(loan=self.loan_a, description="Scan ring",
                metal="GOLD", gross_weight=10, net_weight=9, purity_percentage=90,
                latest_appraised_value=1000, custody_state="IN_VAULT")
        self.user.profile.workspace = self.workspace_b
        self.user.profile.save(update_fields=["workspace"])
        path = f"/w/{self.workspace_a.slug}/loans/collateral/{item.public_id}/scan/"
        target = reverse("workspace_slug_loan_detail", kwargs={"workspace_slug": self.workspace_a.slug, "pk": self.loan_a.pk}) + f"#collateral-{item.public_id}"
        with patch("apps.orgs.views.workspace_slug_loans_dispatch", side_effect=AssertionError("dispatcher used")):
            self.assertRedirects(self.client.get(path), target, fetch_redirect_response=False)
        self.assertRedirects(self.client.get(f"/loans/collateral/{item.public_id}/scan/", HTTP_HOST="phase11-a.test"), target, fetch_redirect_response=False)
        self.assertEqual(self.client.get(f"/w/{self.workspace_b.slug}/loans/collateral/{item.public_id}/scan/").status_code, 404)
        self.assertEqual(self.client.get(path, HTTP_HOST="phase11-b.test").status_code, 403)
        Membership.objects.filter(user=self.user, company=self.workspace_a).delete()
        self.assertEqual(self.client.get(path).status_code, 302)

    def test_batch_search_keeps_workspace_and_legacy_domain_entry_scoped(self):
        from apps.tenant_apps.loans.models import PawnCollateralItem
        for workspace, loan in ((self.workspace_a, self.loan_a), (self.workspace_b, self.loan_b)):
            with workspace_context(workspace.pk):
                PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
                PawnCollateralItem.objects.create(loan=loan, description="Batch search item",
                    metal="GOLD", gross_weight=10, net_weight=9, purity_percentage=90,
                    latest_appraised_value=1000)
        self.user.profile.workspace = self.workspace_b
        self.user.profile.save(update_fields=["workspace"])
        for workspace, loan in ((self.workspace_a, self.loan_a), (self.workspace_b, self.loan_b)):
            url = reverse("workspace_loans:release_batch_search", kwargs={"workspace_slug": workspace.slug})
            response = self.client.get(url)
            self.assertEqual([row["id"] for row in response.json()["results"]], [loan.pk])
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(self.client.post(url).status_code, 405)
        legacy = self.client.get("/loans/releases/batch/new/", HTTP_HOST="phase11-a.test")
        self.assertContains(legacy, f'data-search-url="/w/{self.workspace_a.slug}/loans/releases/batch/search/"')
        self.assertNotContains(legacy, 'href="/loans/')

    def test_direct_browse_pages_and_htmx_keep_workspace_links(self):
        from apps.tenant_apps.loans.models import PawnCollateralItem, PawnLoanEvent, PawnLoanRelease
        with workspace_context(self.workspace_a.pk):
            item = PawnCollateralItem.objects.create(loan=self.loan_a, description="Route gold ring",
                metal="GOLD", gross_weight=10, net_weight=9, purity_percentage=90,
                latest_appraised_value=1000)
            event = PawnLoanEvent.objects.create(loan=self.loan_a, event_kind="RELEASE",
                effective_date=date(2026, 9, 10), payload={"test": True}, payload_fingerprint="route",
                idempotency_key="browse-route")
            release = PawnLoanRelease.objects.create(workspace=self.workspace_a, loan=self.loan_a,
                loan_event=event, release_number="Route-release", request_key="route",
                effective_date=date(2026, 9, 10), settlement_amount=1000,
                principal_amount=1000, interest_amount=0, fee_amount=0)
        self.user.profile.workspace = self.workspace_b
        self.user.profile.save(update_fields=["workspace"])
        for suffix, expected in (("collateral/", "Route gold ring"), ("releases/", "Route-release")):
            url = f"/w/{self.workspace_a.slug}/loans/{suffix}"
            for headers, fragment in (({}, False), ({"HTTP_HX_REQUEST": "true"}, True),
                    ({"HTTP_HX_REQUEST": "true", "HTTP_HX_HISTORY_RESTORE_REQUEST": "true"}, False)):
                with self.subTest(suffix=suffix, headers=headers), patch(
                    "apps.orgs.views.workspace_slug_loans_dispatch", side_effect=AssertionError("dispatcher used"),
                ):
                    response = self.client.get(url, {"q": expected, "sort": "loan", "page": "1"}, **headers)
                    self.assertContains(response, expected)
                    self.assertNotContains(response, 'href="/loans/')
                    self.assertContains(response, reverse('workspace_slug_loan_detail', kwargs={'workspace_slug': self.workspace_a.slug, 'pk': self.loan_a.pk}))
                    if suffix == "collateral/":
                        self.assertContains(response, f'/w/{self.workspace_a.slug}/loans/collateral/{item.public_id}/scan/')
                    else:
                        self.assertContains(response, f'/w/{self.workspace_a.slug}/loans/releases/{release.pk}/')
                    self.assertEqual("<!DOCTYPE html>" in response.content.decode(), not fragment)
                    self.assertIn("HX-Request", response["Vary"])
            foreign = self.client.get(f"/w/{self.workspace_b.slug}/loans/{suffix}")
            self.assertNotContains(foreign, expected)
            self.assertEqual(self.client.post(url).status_code, 405)
        detail = f"/w/{self.workspace_a.slug}/loans/releases/{release.pk}/"
        self.assertEqual(resolve(detail).namespace, "workspace_loans")
        response = self.client.get(detail)
        self.assertContains(response, "Route-release")
        self.assertNotContains(response, 'href="/loans/')
        self.assertEqual(self.client.get(f"/w/{self.workspace_b.slug}/loans/releases/{release.pk}/").status_code, 404)
        self.assertEqual(self.client.get(detail, HTTP_HOST="phase11-b.test").status_code, 403)
        Membership.objects.filter(user=self.user, company=self.workspace_a).delete()
        self.assertEqual(self.client.get(detail).status_code, 302)


    def test_direct_document_routes_preserve_workspace_denial_and_bypass_dispatcher(self):
        from unittest.mock import patch
        with patch("apps.orgs.views.workspace_slug_loans_dispatch", side_effect=AssertionError("legacy dispatch used")):
            own = self.client.get(f"/w/{self.workspace_a.slug}/loans/internal/{self.loan_a.pk}/ticket.pdf")
            self.assertEqual(own.status_code, 409)  # Draft has no issuable ticket.
            wrong = self.client.get(f"/w/{self.workspace_b.slug}/loans/internal/{self.loan_a.pk}/ticket.pdf")
            self.assertEqual(wrong.status_code, 404)
            conflict = self.client.get(f"/w/{self.workspace_b.slug}/loans/internal/{self.loan_b.pk}/ticket.pdf", HTTP_HOST="phase11-a.test")
            self.assertEqual(conflict.status_code, 403)


    def test_remaining_workspace_pages_emit_scoped_links_without_dispatcher(self):
        routes = (
            "pawn_economics_setup", "loan_workflow_settings", "loan_product_list",
            "document_layout_list", "document_layout_create", "document_print_profile_list",
            "document_print_profile_create", "pawn_operations_console", "pawn_operations_runbook",
            "pawn_risk_portfolio", "pawn_loan_reports", "pawn_loan_notice_list",
        )
        with patch("apps.orgs.views.workspace_slug_loans_dispatch", side_effect=AssertionError("dispatcher used")):
            for workspace in (self.workspace_a, self.workspace_b):
                for name in routes:
                    with self.subTest(workspace=workspace.slug, route=name):
                        response = self.client.get(reverse("workspace_loans:" + name, kwargs={
                            "workspace_slug": workspace.slug,
                        }))
                        self.assertEqual(response.status_code, 200)
                        for attribute in ("href", "action", "hx-get", "hx-post"):
                            self.assertNotContains(response, f'{attribute}="/loans/')
                for alias, kwargs in (
                    ("workspace_slug_settings_numbering", {}),
                    ("workspace_slug_loan_list", {}),
                    ("workspace_slug_loan_create", {}),
                    ("workspace_slug_loan_detail", {"pk": self.loan_a.pk if workspace == self.workspace_a else self.loan_b.pk}),
                ):
                    response = self.client.get(reverse(alias, kwargs={"workspace_slug": workspace.slug, **kwargs}))
                    self.assertIn(response.status_code, (200, 302))
        self.assertEqual(self.client.get(f"/w/{self.workspace_a.slug}/loans/unknown-path/").status_code, 404)


class DirectLoansAdapterTests(TestCase):
    def test_adapter_does_not_rewrite_response_content_or_redirects(self):
        from types import SimpleNamespace
        from django.http import HttpResponse, HttpResponseRedirect
        from django.test import RequestFactory
        from apps.orgs.route_adapters import workspace_view
        request = RequestFactory().get("/w/alpha/loans/setup/")
        request.workspace = SimpleNamespace(slug="alpha")
        for response in (HttpResponse(b'<p>Literal "/loans/" evidence</p>'),
                         HttpResponseRedirect("/w/alpha/loans/internal/?q=a%2Fb")):
            content, headers = response.content, dict(response.headers)
            self.assertIs(workspace_view(lambda request: response)(request, "alpha"), response)
            self.assertEqual(response.content, content)
            self.assertEqual(dict(response.headers), headers)

    def test_migrated_routes_resolve_without_dispatch_and_preserve_legacy_paths(self):
        from apps.tenant_apps.loans.workspace_urls import urlpatterns
        from apps.tenant_apps.loans import urls
        samples = {"issue_pk": 21, "product_pk": 22, "return_pk": 23, "version_pk": 24, "auction_pk": 17, "renewal_pk": 18, "asset_pk": 19, "section": "portfolio", "export_format": "csv", "party_pk": 20, "license_pk": 16, "revision_pk": 15, "notice_pk": 14, "observation_pk": 13, "pk": 7, "event_pk": 8, "release_pk": 9, "item_pk": 10, "photo_pk": 11, "batch_pk": 12, "public_id": "12345678-1234-1234-1234-123456789abc"}
        for pattern in urlpatterns:
            legacy = next(p for p in urls.urlpatterns if p.name == pattern.name)
            kwargs = {name: samples[name] for name in pattern.pattern.converters}
            scoped = reverse("workspace_loans:" + pattern.name, kwargs={"workspace_slug": "alpha", **kwargs})
            self.assertEqual(scoped, "/w/alpha" + reverse("loans:" + pattern.name, kwargs=kwargs, urlconf="django_project.workspace_urls"))
            match = resolve(scoped)
            self.assertEqual(match.namespace, "workspace_loans")
            self.assertIs(match.func.__wrapped__, legacy.callback)

    def test_adapter_preserves_streaming_bytes_headers_and_rejects_wrong_workspace(self):
        from types import SimpleNamespace
        from django.http import Http404, StreamingHttpResponse
        from django.test import RequestFactory
        from apps.orgs.route_adapters import workspace_view
        request = RequestFactory().get("/w/alpha/loans/internal/7/ticket.pdf?renderer=fixed")
        request.workspace = SimpleNamespace(slug="alpha")
        response = StreamingHttpResponse([b"binary /loans/ unchanged"], content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="ticket.pdf"'
        response["Cache-Control"] = "private, no-store"
        seen = []
        def view(request, pk):
            seen.append((pk, request.GET["renderer"]))
            return response
        adapter = workspace_view(view)
        self.assertIs(adapter(request, "alpha", pk=7), response)
        self.assertEqual(b"".join(response.streaming_content), b"binary /loans/ unchanged")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        for slug in ("beta", "missing"):
            with self.assertRaises(Http404):
                adapter(request, slug, pk=7)
        self.assertEqual(seen, [(7, "fixed")])
