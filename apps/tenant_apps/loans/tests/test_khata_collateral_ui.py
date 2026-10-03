"""Combined receiving/media failure and searchable group selection boundaries."""
import json
import uuid
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import TestCase, RequestFactory, override_settings
from PIL import Image

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataOperation, KhataCollateralPhoto, KhataCollateralItem
from apps.tenant_apps.loans.services import khata_accounts, khata_opening
from apps.tenant_apps.loans.services.origination_settings import set_collateral_photo_requirement
from apps.tenant_apps.loans.web import khata_items, khata_views, khata_workflows
from .test_khata_corrections import CorrectionFixture
from .test_khata_opening import STORAGES
from .test_khata_foundation import draft_args, fixture


def image_upload(color="white"):
    stream = BytesIO()
    Image.new("RGB", (4, 4), color).save(stream, format="PNG")
    return SimpleUploadedFile("collateral.png", stream.getvalue(), content_type="image/png")


@override_settings(STORAGES=STORAGES)
class KhataCollateralUITests(CorrectionFixture, TestCase):
    def request(self, data=None, method="get", actor=None):
        request = getattr(RequestFactory(), method)("/", data or {})
        request.user = actor or self.actor
        request.workspace = self.workspace
        return request

    def browse(self, **params):
        with workspace_context(self.workspace.pk):
            return khata_items.browse(self.request(dict(format="json", **params)), self.account.pk)

    def receive(self, **changes):
        data = dict(request_key=uuid.uuid4(), description="Received chain", metal="GOLD", quantity=1,
            gross_weight="20", net_weight="19", purity="91.6", storage_reference="Vault B / bag 7",
            received_from="Borrower", receipt_confirmed="on")
        data.update(changes)
        with workspace_context(self.workspace.pk):
            return khata_workflows.operate(self.request(data, "post"), self.account.pk, "deposit")

    def test_combined_receipt_photo_and_retry_preserve_distinct_sources(self):
        key = uuid.uuid4()
        for _ in range(2):
            response = self.receive(request_key=key, upload=image_upload())
            self.assertEqual(response.status_code, 302)
            self.assertIn("/collateral/?received=", response["Location"])
        with workspace_context(self.workspace.pk):
            item = self.account.collateral.get(description="Received chain")
            self.assertEqual(item.photos.count(), 1)
            self.assertEqual(item.received_operation.kind, "DEPOSIT")
            self.assertEqual(item.photos.get().operation.kind, "PHOTO")
            self.assertEqual(self.account.operations.filter(kind="WITHDRAW").count(), 1)
        self.assertContains(self.receive(request_key=key, upload=image_upload("red")), "different instructions")

    def test_invalid_or_unconfirmed_upload_never_receives_an_item(self):
        self.assertContains(self.receive(upload=SimpleUploadedFile("bad.png", b"not an image", content_type="image/png")), "valid JPEG or PNG")
        self.assertContains(self.receive(receipt_confirmed=""), "This field is required")
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.account.collateral.filter(description="Received chain").exists())

    def test_camera_jpeg_receipt_and_latest_private_photo_on_detail(self):
        content = BytesIO()
        Image.new("RGB", (640, 480), "white").save(content, format="JPEG")
        response = self.receive(upload=SimpleUploadedFile("collateral-camera.jpg", content.getvalue(), content_type="image/jpeg"))
        self.assertEqual(response.status_code, 302)
        with workspace_context(self.workspace.pk):
            item = self.account.collateral.get(description="Received chain")
            first = item.photos.get()
            latest = khata_opening.attach_photo(**self.command(), item_id=item.pk, upload=image_upload("red"))
            detail = khata_views.detail(self.request(dict(section="collateral")), self.account.pk)
            self.assertContains(detail, f'/{latest.pk}/?thumbnail=1')
            self.assertNotContains(detail, f'/{first.pk}/?thumbnail=1')
            self.assertContains(detail, f'collateral-item-{item.public_id}')
            self.assertEqual(first.operation.kind, "PHOTO")

    def test_partial_storage_write_failure_rolls_back_rows_and_file(self):
        storage = KhataCollateralPhoto._meta.get_field("file").storage
        saved = []
        original = storage.save
        def failing_save(name, content, *args, **kwargs):
            saved.append(original(name, content, *args, **kwargs))
            raise OSError("Fictional storage outage")
        with patch.object(storage, "save", side_effect=failing_save):
            self.assertContains(self.receive(upload=image_upload()), "Fictional storage outage")
        self.assertEqual(len(saved), 1)
        self.assertFalse(storage.exists(saved[0]))
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.account.collateral.filter(description="Received chain").exists())
            self.assertFalse(KhataCollateralPhoto.objects.exists())

    def test_photo_row_failure_cleans_private_file_and_receipt(self):
        storage = KhataCollateralPhoto._meta.get_field("file").storage
        saved = []
        original = storage.save
        def tracking_save(name, content, *args, **kwargs):
            path = original(name, content, *args, **kwargs)
            saved.append(path)
            return path
        with patch.object(storage, "save", side_effect=tracking_save), patch.object(KhataCollateralPhoto, "full_clean", side_effect=ValidationError("Photo persistence refused")):
            self.assertContains(self.receive(upload=image_upload()), "Photo persistence refused")
        self.assertFalse(storage.exists(saved[0]))
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.account.collateral.filter(description="Received chain").exists())

    def test_required_photo_allows_receipt_but_refuses_approval_until_attached(self):
        with workspace_context(self.workspace.pk):
            set_collateral_photo_requirement(workspace=self.workspace, actor=self.actor, required=True)
        self.account = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.assertEqual(self.receive().status_code, 302)
        with self.assertRaisesRegex(ValueError, "requires a photograph"):
            self.approve()
        with workspace_context(self.workspace.pk):
            item = self.account.collateral.get()
        self.photo(item)
        self.approve()

    def test_save_add_another_and_return_exchange_keep_ids_without_auto_selection(self):
        self.assertIn("/actions/deposit/?received=", self.receive(add_another="1")["Location"])
        incoming = self.replacement()
        response = self.receive(return_to="exchange", exchange_outgoing=[self.first.pk], exchange_incoming=[incoming.pk])
        location = response["Location"]
        self.assertIn("/actions/exchange/?", location)
        self.assertIn(f"outgoing={self.first.pk}", location)
        self.assertIn(f"incoming={incoming.pk}", location)
        self.assertIn("suggest=", location)
        self.assertNotIn("https:", location)

    def test_hundreds_of_items_have_bounded_pages_and_stable_search(self):
        for n in range(202):
            self.deposit(description="Similar gold chain", storage_reference=f"Vault / bag {n:03}")
        result = json.loads(self.browse(sort="oldest").content)
        self.assertEqual(result["count"], 203)
        self.assertEqual(len(result["items"]), 25)
        self.assertEqual(result["items"][0]["id"], self.first.pk)
        next_page = json.loads(self.browse(sort="oldest", page=2).content)
        self.assertFalse({i["id"] for i in result["items"]} & {i["id"] for i in next_page["items"]})
        result = json.loads(self.browse(q="bag 099").content)
        self.assertEqual(result["count"], 1)
        self.assertEqual(json.loads(self.browse(q=str(self.first.public_id)).content)["items"][0]["id"], self.first.pk)
        by_id = json.loads(self.browse(q=str(self.first.pk)).content)
        self.assertEqual(by_id["count"], 1)
        self.assertEqual(by_id["items"][0]["id"], self.first.pk)
        self.assertEqual(json.loads(self.browse(metal="SILVER").content)["count"], 0)
        self.assertEqual(self.browse(from_date="bad-date").status_code, 400)

    def test_custody_and_incoming_reuse_filter_follow_sources(self):
        incoming = self.replacement()
        operation = self.exchange([self.first], [incoming])
        rows = json.loads(self.browse().content)["items"]
        self.assertEqual(next(r for r in rows if r["id"] == self.first.pk)["custody"], "Return pending")
        self.assertEqual(json.loads(self.browse(mode="outgoing").content)["items"][0]["id"], incoming.pk)
        self.assertEqual(json.loads(self.browse(mode="incoming").content)["count"], 0)
        self.handover(self.first, operation)
        self.assertEqual(json.loads(self.browse(custody="returned").content)["items"][0]["id"], self.first.pk)

    def test_same_workspace_other_account_is_not_in_search_or_selections(self):
        other = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        foreign = khata_opening.record_deposit(**dict(self.command(), account_id=other.pk), description="Other account item", metal="GOLD",
            quantity=1, gross_weight="20", net_weight="20", purity="100", storage_reference="Other vault", received_from="Borrower")
        self.assertEqual(json.loads(self.browse(q=str(foreign.public_id)).content)["count"], 0)
        with workspace_context(self.workspace.pk):
            response = khata_workflows.operate(self.request(dict(request_key=uuid.uuid4(), outgoing=[self.first.pk], incoming=[foreign.pk], reason="Exchange"), "post"), self.account.pk, "exchange")
            self.assertContains(response, "Select a valid choice")
        viewer = self.staff()
        with workspace_context(self.workspace.pk), self.assertRaises(PermissionDenied):
            khata_workflows.operate(self.request(method="get", actor=viewer), self.account.pk, "deposit")

    def test_photo_and_suggested_values_are_private_and_missing_quotes_are_not_zero(self):
        photo = self.photo(self.first)
        result = json.loads(self.browse().content)["items"][0]
        self.assertIn(f"/photos/{photo.pk}/", result["photo"])
        self.assertIsNotNone(result["value"])
        with self.later(0, 1):
            self.assertIsNone(json.loads(self.browse().content)["items"][0]["value"])
        self.assertIn("no-store", self.browse()["Cache-Control"])

    def test_thumbnail_checks_original_integrity_and_does_not_change_it(self):
        photo = self.photo(self.first)
        with workspace_context(self.workspace.pk):
            response = khata_workflows.photo(self.request(dict(thumbnail="1")), self.account.pk, photo.pk)
            self.assertEqual(response["Content-Type"], "image/jpeg")
            self.assertIn("no-store", response["Cache-Control"])
            with Image.open(BytesIO(response.content)) as thumbnail:
                self.assertLessEqual(thumbnail.width, 160)
                self.assertLessEqual(thumbnail.height, 120)
            original = khata_workflows.photo(self.request(), self.account.pk, photo.pk)
            self.assertEqual(original["Content-Type"], "image/png")
            self.assertNotEqual(response.content, original.content)
            photo.file.storage.delete(photo.file.name)
            self.assertEqual(khata_workflows.photo(self.request(dict(thumbnail="1")), self.account.pk, photo.pk).status_code, 409)

    def test_browser_refuses_another_workspace_account(self):
        workspace, actor, borrower = fixture(uuid.uuid4().hex[:8])
        series = khata_accounts.create_series(workspace=workspace, actor=actor, code="KH", name="Other Khata")
        other = khata_accounts.create_draft(**draft_args(workspace, actor, borrower, series))
        with workspace_context(self.workspace.pk), self.assertRaises(Http404):
            khata_items.browse(self.request(dict(format="json")), other.pk)
