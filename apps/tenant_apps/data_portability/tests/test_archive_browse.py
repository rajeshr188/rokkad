import copy
from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from apps.tenancy import testing
from apps.orgs.models import Membership, WorkspaceRoleGrant
from apps.tenant_apps.loans.models import HistoricalLoanEvidence, PawnLoan, PawnLoanEvent
from apps.tenant_apps.loans.selectors.archive import historical_loan_details
from apps.tenant_apps.loans.services.archive import accept_evidence
from apps.tenant_apps.loans.services.history_contract import digest
from .fixtures import PortabilityFixture
from .test_loan_archive import document


def legacy_document():
    value = document()
    system = "legacy:synthetic:jcl"
    value["source"].update(system=system, loan_id="girvi_loan:1")
    value["facts"].update(loan_number="C00123", original_principal=None, opened_on="2021-01-01",
                          closed_on="2021-02-01", borrower_reference={"system": system, "id": "contact_customer:2"},
                          collateral=[{"description": "Gold chain", "quantity": 1,
                                       "net_weight": "10", "gross_weight": None}],
                          payments=[{"id": "girvi_loanpayment:4", "date": "2021-02-01", "amount": "1020"}])

    def row(table, pk, **facts):
        return {"source": {"source_system": system, "table": table, "id": pk,
                            "external_id": f"{table}:{pk}"}, "facts": facts}

    value["source_records"] = [
        row("girvi_loan", "1", loan_amount="0", customer_id="2", series_id="3", tenure="3",
            item_desc="Gold chain", interest_type="Simple"),
        row("girvi_loanitem", "5", loan_id="1", itemdesc="Gold chain", itemtype="Gold", weight="10",
            purity="91.6", loanamount="1000", interestrate="2", interest="20", quantity="1"),
        row("girvi_loanpayment", "4", loan_id="1", payment_amount="1020", principal_payment="1000",
            interest_payment="20", payment_date="2021-02-01 00:00:00+00", with_release="t"),
        row("girvi_release", "6", loan_id="1", release_id="REL001", released_by_id="2",
            release_date="2021-02-01 00:00:00+00", created_by_id="old-operator"),
        row("contact_customer", "2", name="Synthetic former borrower", relatedto="Synthetic parent"),
        row("girvi_series", "3", name="C", license_id="7"),
        row("girvi_license", "7", name="Old licence", shopname="Synthetic lender"),
    ]
    return value


class ArchivePresenterTests(SimpleTestCase):
    def test_legacy_details_preserve_amounts_item_terms_payment_splits_and_release(self):
        value = legacy_document()
        before = copy.deepcopy(value)
        details = historical_loan_details(value)
        self.assertEqual(details["stored_amount"], "0")
        self.assertEqual(details["closed_on"], date(2021, 2, 1))
        self.assertEqual(details["payments"][0]["date"], date(2021, 2, 1))
        groups = details["source_groups"]
        self.assertIn({"label": "Recorded principal payment", "value": "1000"}, groups["payments"][0]["fields"])
        self.assertIn({"label": "Recorded interest rate", "value": "2"}, groups["items"][0]["fields"])
        self.assertIn({"label": "Release number", "value": "REL001"}, groups["releases"][0]["fields"])
        self.assertIn({"label": "Recipient name (source snapshot)", "value": "Synthetic former borrower"},
                      groups["releases"][0]["fields"])
        self.assertEqual(len(groups["setup"]), 2)
        self.assertEqual(value, before)
        self.assertEqual(digest(value), digest(before))
        self.assertIsNone(value["facts"]["original_principal"])

    def test_generic_archive_needs_no_legacy_graph(self):
        details = historical_loan_details(document())
        self.assertIsNone(details["stored_amount"])
        self.assertIsNone(details["payments"])
        self.assertFalse(any(details["source_groups"].values()))

    def test_zero_empty_and_unknown_remain_distinct(self):
        value = document()
        value["facts"].update(payments=[], collateral=[])
        details = historical_loan_details(value)
        self.assertEqual(details["payments"], [])
        self.assertEqual(details["collateral"], [])
        value["facts"]["payments"] = [{"id": "p0", "date": None, "amount": "0"}]
        self.assertEqual(historical_loan_details(value)["payments"][0]["amount"], "0")

    def test_foreign_unbound_and_duplicate_origins_are_not_promoted(self):
        for mutate in (lambda d: d["source_records"][0]["source"].update(source_system="foreign"),
                       lambda d: d["source_records"].append(copy.deepcopy(d["source_records"][0]))):
            value = legacy_document()
            mutate(value)
            self.assertFalse(any(historical_loan_details(value)["source_groups"].values()))
        value = legacy_document()
        value["source_records"][1]["facts"]["loan_id"] = "other-loan"
        value["source_records"][2]["source"]["external_id"] = "incorrect"
        details = historical_loan_details(value)
        self.assertEqual(details["source_groups"]["items"], [])
        self.assertEqual(details["source_groups"]["payments"], [])
        self.assertEqual(len(details["source_groups"]["releases"]), 1)

    def test_unrelated_or_nested_raw_rows_are_not_guessed_as_fields(self):
        value = legacy_document()
        value["source_records"][0]["facts"]["nested"] = {"unrelated": "record"}
        value["source_records"].extend([{"source": "opaque", "facts": []}, {"adapter": "custom"}])
        self.assertNotIn("Nested", [field["label"] for field in historical_loan_details(value)["source_groups"]["loan"][0]["fields"]])


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ArchiveBrowseTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        self.client.force_login(self.actor)

    def accept(self, value):
        return accept_evidence(workspace_id=self.a.pk, actor=self.actor, document=value,
                               expected_sha256=digest(value), confirmed=True)

    def url(self, name, **kwargs):
        return reverse("workspace_portability:" + name, kwargs={"workspace_slug": self.a.slug, **kwargs})

    def test_readable_detail_is_escaped_read_only_and_exports_identically(self):
        value = legacy_document()
        value["source_records"][1]["facts"]["itemdesc"] = "<script>bad()</script>"
        with self.scoped():
            evidence = self.accept(value)
            before = digest(evidence.document)
        response = self.client.get(self.url("archive_detail", evidence_id=evidence.public_id))
        for text in ("Source record C00123", "01/02/2021", "Gold chain", "Recorded principal payment",
                     "Recorded interest payment", "REL001", "Old-system customer details",
                     "Stored loan amount (old system)", "may have changed during servicing"):
            self.assertContains(response, text)
        self.assertNotContains(response, "<script>bad()</script>")
        self.assertContains(response, "&lt;script&gt;bad()&lt;/script&gt;")
        self.assertIn("no-store", response["Cache-Control"])
        with self.scoped():
            evidence.refresh_from_db()
            self.assertEqual(digest(evidence.document), before)
            self.assertEqual(evidence.document, value)
            self.assertFalse(PawnLoan.objects.exists())
            self.assertFalse(PawnLoanEvent.objects.exists())
        exported = self.client.post(self.url("archive_export", evidence_id=evidence.public_id))
        import json
        self.assertEqual(json.loads(exported.content), value)

    def test_customer_search_dates_and_pagination_keep_all_matching_records(self):
        with self.scoped():
            for index in range(26):
                value = document()
                value["source"].update(loan_id=f"L{index}")
                value["facts"].update(loan_number=f"L{index}", borrower_name="Unique former customer",
                                      closed_on="1990-02-01")
                self.accept(value)
        listing = self.url("archive_list")
        first = self.client.get(listing, {"q": "unique FORMER"})
        self.assertContains(first, "26 retained records")
        self.assertContains(first, "01/02/1990")
        self.assertEqual(len(first.context["archive_rows"]), 25)
        self.assertContains(first, "q=unique%20FORMER")
        second = self.client.get(listing, {"q": "unique FORMER", "page": 2})
        self.assertEqual(len(second.context["archive_rows"]), 1)
        self.assertNotContains(self.client.get(listing, {"q": "no-match"}), "Unique former customer")
        self.assertContains(self.client.get(listing, {"q": "L25"}), "L25")

    def test_reader_needs_no_import_rights_and_foreign_detail_stays_unavailable(self):
        with self.scoped():
            evidence = self.accept(document())
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                permission__codename__in=["data_import", "workspace_settings"]).delete()
        response = self.client.get(self.url("archive_detail", evidence_id=evidence.public_id))
        self.assertContains(response, "Payment history is unknown")
        self.assertNotContains(self.client.get(self.url("archive_list")), "Upload historical evidence for review")
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.b))
        foreign_url = reverse("workspace_portability:archive_detail", kwargs={
            "workspace_slug": self.b.slug, "evidence_id": evidence.public_id})
        self.assertEqual(self.client.get(foreign_url).status_code, 403)
        with self.scoped():
            self.assertEqual(HistoricalLoanEvidence.objects.count(), 1)
