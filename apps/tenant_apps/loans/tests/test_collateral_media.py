from apps.tenancy.testing import workspace_role_permissions
import hashlib
import shutil
import tempfile
import uuid
from datetime import date
from decimal import Decimal

import fitz
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.staticfiles.storage import StaticFilesStorage, staticfiles_storage
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from apps.tenancy.testing import WorkspaceTestCase

from apps.orgs.models import Membership, Role
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanOperationalNotice,
    LoanSeries,
    PawnCollateralItem,
    PawnCollateralLabelIssue,
    PawnCollateralPhoto,
    PawnCollateralStorageMovement,
    PawnPhysicalVerificationObservation,
    PawnPhysicalVerificationResolution,
    PawnLoan,
    PawnStorageLocation,
)
from apps.tenant_apps.loans.services import (
    PawnCollateralMediaError,
    PawnLifecycleError,
    append_collateral_photo,
    approve_pawn_loan,
    create_storage_location,
    place_or_transfer_collateral,
    remove_collateral_from_storage,
    PawnStorageError,
    PawnPhysicalVerificationBlockerError,
    PawnPhysicalVerificationError,
    assert_physical_verification_clear,
    complete_physical_verification,
    record_physical_verification_observation,
    resolve_physical_verification_discrepancy,
    start_physical_verification,
)
from apps.tenant_apps.notify_v2.models import NotificationJob
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="rokkad-collateral-media-")


@override_settings(
    ROOT_URLCONF="django_project.workspace_urls",
    DEBUG=True,
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class PawnCollateralMediaTests(WorkspaceTestCase):
    test_schema_name = f"loans_media_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-media-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="loans-media-owner",
            defaults={"email": "loans-media-owner@example.com"},
        )
        tenant.name = f"Loans Media {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        super().setUp()
        # The process-level lazy storage may have been initialized by the
        # production manifest backend before this class override took effect.
        staticfiles_storage._wrapped = StaticFilesStorage()
        self.owner = self.tenant.owner
        self.start_active_trial()
        role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=self.owner,
            company=self.tenant,
            defaults={"role": role},
        )
        borrower = Party.objects.create(display_name="Media Borrower")
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Media License",
            license_number="MEDIA-1",
            issuing_authority="Authority",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        series = LoanSeries.objects.create(license=license, code="M", name="Media")
        self.loan = PawnLoan.objects.create(
            workspace=self.tenant,
            license=license,
            series=series,
            product_version=ensure_test_product_version(self.tenant),
            borrower=borrower,
            loan_number="PL-M-1",
            principal_amount=Decimal("5000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 8, 9),
            tenure_months=3,
        )
        self.item = PawnCollateralItem.objects.create(
            loan=self.loan,
            description="Gold ring",
            metal="GOLD",
            gross_weight=Decimal("2.1000"),
            net_weight=Decimal("2.0000"),
            purity_percentage=Decimal("91.6000"),
        )
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)

    @staticmethod
    def photo(name="ring.jpg"):
        return SimpleUploadedFile(
            name,
            b"\xff\xd8\xff\xe0" + b"collateral-evidence",
            content_type="image/jpeg",
        )

    def test_approval_requires_photo_and_freezes_photo_hash(self):
        with self.assertRaisesRegex(PawnLifecycleError, "requires at least one photograph"):
            approve_pawn_loan(self.loan.pk, actor=self.owner)

        photo = append_collateral_photo(
            self.item.pk,
            upload=self.photo(),
            actor=self.owner,
        )
        snapshot = approve_pawn_loan(self.loan.pk, actor=self.owner)

        evidence = snapshot.payload["collateral"][0]["photo_evidence"][0]
        self.assertEqual(evidence["photo_id"], photo.pk)
        self.assertEqual(evidence["sha256"], photo.sha256)
        with self.assertRaises(ValidationError):
            photo.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnCollateralPhoto.objects.filter(pk=photo.pk).update(
                original_filename="changed.jpg"
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnCollateralItem.objects.filter(pk=self.item.pk).update(
                public_id=uuid.uuid4()
            )

    def test_draft_photo_delete_is_post_only_and_blocks_approval_until_replaced(self):
        photo = append_collateral_photo(self.item.pk, upload=self.photo(), actor=self.owner)
        storage, name = photo.file.storage, photo.file.name
        url = reverse("loans:pawn_collateral_photo_delete", args=[self.loan.pk, self.item.pk, photo.pk])
        self.assertContains(self.client.get(reverse("loans:pawn_loan_detail", args=[self.loan.pk])), "Delete photo")
        self.assertEqual(self.client.get(url).status_code, 405)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(PawnCollateralPhoto.objects.filter(pk=photo.pk).exists())
        self.assertFalse(storage.exists(name))
        self.assertTrue(self.loan.change_log.filter(metadata__action="collateral_photo_deleted").exists())
        with self.assertRaisesRegex(PawnLifecycleError, "requires at least one photograph"):
            approve_pawn_loan(self.loan.pk, actor=self.owner)
        append_collateral_photo(self.item.pk, upload=self.photo("replacement.jpg"), actor=self.owner)
        approve_pawn_loan(self.loan.pk, actor=self.owner)

    def test_photo_delete_preserves_approved_evidence_and_rejects_wrong_item(self):
        from apps.tenant_apps.loans.services.collateral_media import delete_draft_collateral_photo
        photo = append_collateral_photo(self.item.pk, upload=self.photo(), actor=self.owner)
        wrong = reverse("loans:pawn_collateral_photo_delete", args=[self.loan.pk, self.item.pk + 999999, photo.pk])
        self.assertEqual(self.client.post(wrong).status_code, 404)
        approve_pawn_loan(self.loan.pk, actor=self.owner)
        with self.assertRaisesRegex(PawnCollateralMediaError, "only be deleted"):
            delete_draft_collateral_photo(self.item.pk, photo.pk, actor=self.owner)
        self.assertNotContains(self.client.get(reverse("loans:pawn_loan_detail", args=[self.loan.pk])), "Delete photo")
        url = reverse("loans:pawn_collateral_photo_delete", args=[self.loan.pk, self.item.pk, photo.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertTrue(PawnCollateralPhoto.objects.filter(pk=photo.pk).exists())
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnCollateralPhoto.objects.filter(pk=photo.pk).delete()

    def test_photo_delete_rollback_preserves_record_and_file(self):
        from apps.tenant_apps.loans.services.collateral_media import delete_draft_collateral_photo
        photo = append_collateral_photo(self.item.pk, upload=self.photo(), actor=self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                delete_draft_collateral_photo(self.item.pk, photo.pk, actor=self.owner)
                raise RuntimeError("rollback")
        self.assertTrue(PawnCollateralPhoto.objects.filter(pk=photo.pk).exists())
        self.assertTrue(photo.file.storage.exists(photo.file.name))

    def test_photo_delete_keeps_shared_renewal_file(self):
        from apps.tenant_apps.loans.services.collateral_media import delete_draft_collateral_photo, inherit_collateral_photos
        source = append_collateral_photo(self.item.pk, upload=self.photo(), actor=self.owner)
        copy = inherit_collateral_photos(self.item, self.item, actor=self.owner)[0]
        with self.assertRaisesRegex(PawnCollateralMediaError, "renewal evidence"):
            delete_draft_collateral_photo(self.item.pk, source.pk, actor=self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            delete_draft_collateral_photo(self.item.pk, copy.pk, actor=self.owner)
        self.assertTrue(source.file.storage.exists(source.file.name))
        self.assertTrue(PawnCollateralPhoto.objects.filter(pk=source.pk).exists())

    def test_removing_draft_item_preserves_inherited_file(self):
        from apps.tenant_apps.loans.services.collateral_media import inherit_collateral_photos
        from apps.tenant_apps.loans.services.pawn_drafts import _delete_draft_collateral
        source = append_collateral_photo(self.item.pk, upload=self.photo(), actor=self.owner)
        other = PawnCollateralItem.objects.create(loan=self.loan, description="Inherited ring", metal="GOLD",
            gross_weight=2, net_weight=2, purity_percentage=90)
        inherit_collateral_photos(self.item, other, actor=self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            _delete_draft_collateral(other)
        self.assertTrue(source.file.storage.exists(source.file.name))
        self.assertTrue(PawnCollateralPhoto.objects.filter(pk=source.pk).exists())

    def test_viewer_cannot_mutate_draft_or_append_photo(self):
        viewer = get_user_model().objects.create_user(username="draft-read-only")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(user=viewer, company=self.tenant, role=role)
        self.client.force_login(viewer)
        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[self.loan.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, "Append photograph")
        for action in ("pawn_loan_cancel", "pawn_loan_reopen", "pawn_loan_split"):
            with self.subTest(action=action):
                url = reverse("loans:" + action, args=[self.loan.pk])
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {"reason": "Forged mutation"}).status_code, 403)
        url = reverse("loans:pawn_collateral_photo_add", args=[self.loan.pk, self.item.pk])
        self.assertEqual(self.client.post(url, {"photograph": self.photo()}).status_code, 403)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "DRAFT")
        self.assertFalse(self.item.photos.exists())
        self.assertFalse(self.loan.change_log.exists())

    def test_edit_permission_without_create_cannot_split_draft(self):
        from django.contrib.auth.models import Permission
        editor = get_user_model().objects.create_user(username="draft-editor-only")
        role = Role.objects.create(name="Draft editor only")
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(self.tenant)
        for code in ("data_view", "data_edit"):
            permission, _ = Permission.objects.get_or_create(content_type=content_type, codename=code, defaults={"name": code})
            workspace_role_permissions(role, self.tenant).add(permission)
        Membership.objects.create(user=editor, company=self.tenant, role=role)
        self.client.force_login(editor)
        url = reverse("loans:pawn_collateral_photo_add", args=[self.loan.pk, self.item.pk])
        self.assertEqual(self.client.post(url, {"photograph": self.photo()}).status_code, 302)
        self.assertTrue(self.item.photos.exists())
        split_url = reverse("loans:pawn_loan_split", args=[self.loan.pk])
        self.assertEqual(self.client.post(split_url).status_code, 403)

    def test_photo_delete_requires_edit_permission(self):
        photo = append_collateral_photo(self.item.pk, upload=self.photo(), actor=self.owner)
        viewer = get_user_model().objects.create_user(username="photo-viewer")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(user=viewer, company=self.tenant, role=role)
        self.client.force_login(viewer)
        url = reverse("loans:pawn_collateral_photo_delete", args=[self.loan.pk, self.item.pk, photo.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(PawnCollateralPhoto.objects.filter(pk=photo.pk).exists())

    def test_invalid_photo_is_rejected_without_evidence(self):
        with self.assertRaisesRegex(PawnCollateralMediaError, "valid JPEG or PNG"):
            append_collateral_photo(
                self.item.pk,
                upload=SimpleUploadedFile(
                    "fake.jpg", b"not-an-image", content_type="image/jpeg"
                ),
                actor=self.owner,
            )
        self.assertFalse(PawnCollateralPhoto.objects.exists())

    def test_label_contains_identity_and_scan_opens_owning_loan(self):
        response = self.client.get(
            reverse(
                "loans:pawn_collateral_label_pdf",
                args=[self.loan.pk, self.item.pk],
            ),
            {"action": "PRINT"},
        )
        self.assertEqual(response.status_code, 200)
        text = "".join(page.get_text() for page in fitz.open(stream=response.content, filetype="pdf"))
        self.assertIn(self.loan.loan_number, text)
        self.assertIn(f"CI-{str(self.item.public_id).replace('-', '')[:12].upper()}", text)
        self.assertIn("Gold ring", text)
        self.assertIn("Media Borrower", text)
        self.assertIn("Weight: 2.0000 g", text)
        issue = PawnCollateralLabelIssue.objects.get()
        self.assertEqual(issue.action, "PRINT")
        self.assertTrue(
            issue.qr_target.endswith(
                reverse("loans:pawn_collateral_scan", args=[self.item.public_id])
            )
        )
        self.assertEqual(
            issue.payload_sha256,
            hashlib.sha256(response.content).hexdigest(),
        )

        scan = self.client.get(
            reverse("loans:pawn_collateral_scan", args=[self.item.public_id])
        )
        self.assertRedirects(
            scan,
            f"{reverse('loans:pawn_loan_detail', args=[self.loan.pk])}#collateral-{self.item.public_id}",
            fetch_redirect_response=False,
        )

    def test_required_storage_hierarchy_and_owner_only_transfer(self):
        branch = self._location("BRANCH", "BR-1", None)
        vault = self._location("VAULT", "V-1", branch)
        cabinet = self._location("CABINET", "C-1", vault)
        box = self._location("BOX", "B-1", cabinet, capacity=1)
        slot = self._location("SLOT", "S-1", box)

        with self.assertRaises(ValidationError):
            PawnStorageLocation.objects.create(
                workspace=self.tenant,
                parent=branch,
                level="BOX",
                code="SKIP",
                name="Skipped hierarchy",
            )
        outsider = get_user_model().objects.create_user(
            username=f"storage-outsider-{uuid.uuid4().hex[:8]}"
        )
        with self.assertRaisesRegex(PawnStorageError, "Owner"):
            place_or_transfer_collateral(
                self.item.pk,
                destination_id=box.pk,
                reason="",
                actor=outsider,
            )

        placement = place_or_transfer_collateral(
            self.item.pk,
            destination_id=box.pk,
            reason="",
            actor=self.owner,
        )
        self.item.refresh_from_db()
        self.assertEqual(placement.kind, "PLACEMENT")
        self.assertEqual(self.item.current_storage_location, box)

        transfer = place_or_transfer_collateral(
            self.item.pk,
            destination_id=slot.pk,
            reason="Move to dedicated slot",
            actor=self.owner,
        )
        self.item.refresh_from_db()
        self.assertEqual(transfer.from_location, box)
        self.assertEqual(self.item.current_storage_location, slot)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnCollateralStorageMovement.objects.filter(pk=transfer.pk).update(
                reason="changed"
            )
        removal = remove_collateral_from_storage(
            self.item,
            workflow_source="RELEASE",
            source_reference="release-1",
            actor=self.owner,
        )
        self.item.refresh_from_db()
        self.assertEqual(removal.from_location, slot)
        self.assertIsNone(self.item.current_storage_location_id)

    def test_storage_label_and_destination_scan(self):
        branch = self._location("BRANCH", "BR-2", None)
        vault = self._location("VAULT", "V-2", branch)
        cabinet = self._location("CABINET", "C-2", vault)
        box = self._location("BOX", "B-2", cabinet)

        label = self.client.get(
            reverse("loans:pawn_storage_location_label", args=[box.pk])
        )
        self.assertEqual(label.status_code, 200)
        text = "".join(page.get_text() for page in fitz.open(stream=label.content, filetype="pdf"))
        self.assertIn("B-2", text)

        scan = self.client.get(
            reverse("loans:pawn_storage_location_scan", args=[box.public_id]),
            {"item": self.item.public_id},
        )
        self.assertRedirects(
            scan,
            f"{reverse('loans:pawn_collateral_storage_transfer', args=[self.loan.pk, self.item.pk])}?destination={box.pk}",
            fetch_redirect_response=False,
        )

        item_scan = self.client.get(
            reverse("loans:pawn_collateral_scan", args=[self.item.public_id])
        )
        self.assertEqual(item_scan.status_code, 302)
        destination_scan = self.client.get(
            reverse("loans:pawn_storage_location_scan", args=[box.public_id])
        )
        self.assertRedirects(
            destination_scan,
            f"{reverse('loans:pawn_collateral_storage_transfer', args=[self.loan.pk, self.item.pk])}?destination={box.pk}",
            fetch_redirect_response=False,
        )

        transfer_form = self.client.get(destination_scan.url)
        self.assertContains(transfer_form, "This item is selected for storage")
        self.assertEqual(
            transfer_form.context["form"]["destination"].value(),
            str(box.pk),
        )

    def test_storage_movement_history_is_visible_on_loan_detail(self):
        branch = self._location("BRANCH", "BR-H", None)
        vault = self._location("VAULT", "V-H", branch)
        cabinet = self._location("CABINET", "C-H", vault)
        box = self._location("BOX", "B-H", cabinet)
        place_or_transfer_collateral(
            self.item.pk, destination_id=box.pk, reason="", actor=self.owner
        )

        response = self.client.get(
            reverse("loans:pawn_loan_detail", args=[self.loan.pk])
        )

        self.assertContains(response, "Storage movement history")
        self.assertContains(response, "Initial placement")
        self.assertContains(response, "BR-H / V-H / C-H / B-H")

    def test_verification_freezes_scope_blocks_operations_and_requires_loss_compensation(self):
        branch = self._location("BRANCH", "BR-V1", None)
        vault = self._location("VAULT", "V-V1", branch)
        cabinet = self._location("CABINET", "C-V1", vault)
        box = self._location("BOX", "B-V1", cabinet)
        place_or_transfer_collateral(
            self.item.pk, destination_id=box.pk, reason="", actor=self.owner
        )
        outsider = get_user_model().objects.create_user(
            username=f"verification-outsider-{uuid.uuid4().hex[:8]}"
        )
        with self.assertRaisesRegex(PawnPhysicalVerificationError, "Owner"):
            start_physical_verification(scope_location_id=vault.pk, actor=outsider)

        session = start_physical_verification(
            scope_location_id=vault.pk, actor=self.owner
        )
        expectation = session.expectations.get()
        self.assertEqual(expectation.expected_location, box)
        with self.assertRaisesRegex(PawnPhysicalVerificationError, "remain"):
            complete_physical_verification(session.pk, actor=self.owner)
        observation = record_physical_verification_observation(
            session.pk,
            collateral_item_id=self.item.pk,
            classification="MISSING",
            actor=self.owner,
        )
        complete_physical_verification(session.pk, actor=self.owner)
        with self.assertRaises(PawnPhysicalVerificationBlockerError):
            assert_physical_verification_clear(
                (self.item.pk,), operation="PawnLoan release"
            )
        with self.assertRaisesRegex(PawnStorageError, "physical-verification"):
            place_or_transfer_collateral(
                self.item.pk,
                destination_id=box.pk,
                reason="Attempt while missing",
                actor=self.owner,
            )
        with self.assertRaisesRegex(PawnPhysicalVerificationError, "market value"):
            resolve_physical_verification_discrepancy(
                observation.pk,
                outcome="LOST_COMPENSATED",
                reason="Search exhausted",
                actor=self.owner,
            )
        resolution = resolve_physical_verification_discrepancy(
            observation.pk,
            outcome="LOST_COMPENSATED",
            reason="Search exhausted and settlement negotiated",
            current_market_value="6500",
            agreed_compensation="6000",
            compensation_reference="CASH-SETTLEMENT-1",
            actor=self.owner,
        )
        self.assertEqual(
            resolution.outcome,
            PawnPhysicalVerificationResolution.Outcome.LOST_COMPENSATED,
        )
        assert_physical_verification_clear(
            (self.item.pk,), operation="Resolved verification check"
        )
        self.item.refresh_from_db()
        self.assertIsNone(self.item.current_storage_location_id)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnPhysicalVerificationObservation.objects.filter(pk=observation.pk).update(
                notes="changed"
            )

    def test_misplaced_resolution_corrects_location_and_qr_selects_session_item(self):
        branch = self._location("BRANCH", "BR-V2", None)
        vault = self._location("VAULT", "V-V2", branch)
        cabinet = self._location("CABINET", "C-V2", vault)
        expected_box = self._location("BOX", "B-V2A", cabinet)
        observed_box = self._location("BOX", "B-V2B", cabinet)
        place_or_transfer_collateral(
            self.item.pk, destination_id=expected_box.pk, reason="", actor=self.owner
        )
        session = start_physical_verification(
            scope_location_id=vault.pk, actor=self.owner
        )
        observation = record_physical_verification_observation(
            session.pk,
            collateral_item_id=self.item.pk,
            classification="MISPLACED",
            observed_location_id=observed_box.pk,
            notes="Found in adjacent box",
            actor=self.owner,
        )
        complete_physical_verification(session.pk, actor=self.owner)
        resolve_physical_verification_discrepancy(
            observation.pk,
            outcome="LOCATION_CORRECTED",
            reason="Projection corrected to physically observed location",
            actor=self.owner,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_storage_location, observed_box)
        assert_physical_verification_clear(
            (self.item.pk,), operation="Storage transfer"
        )

        scan = self.client.get(
            reverse("loans:pawn_collateral_scan", args=[self.item.public_id]),
            {"verification": session.public_id},
        )
        self.assertRedirects(
            scan,
            f"{reverse('loans:pawn_physical_verification_detail', args=[session.pk])}?item={self.item.pk}",
            fetch_redirect_response=False,
        )

    def test_verification_screen_guides_completion_and_preserves_one_alert_intent(self):
        branch = self._location("BRANCH", "BR-V3", None)
        vault = self._location("VAULT", "V-V3", branch)
        cabinet = self._location("CABINET", "C-V3", vault)
        expected_box = self._location("BOX", "B-V3A", cabinet)
        observed_box = self._location("BOX", "B-V3B", cabinet)
        place_or_transfer_collateral(
            self.item.pk, destination_id=expected_box.pk, reason="", actor=self.owner
        )
        session = start_physical_verification(
            scope_location_id=vault.pk, actor=self.owner
        )
        detail_url = reverse(
            "loans:pawn_physical_verification_detail", args=[session.pk]
        )

        pending = self.client.get(detail_url)
        self.assertContains(pending, "Frozen items")
        self.assertContains(pending, "Observe 1 pending item first.")
        self.assertContains(pending, "Record found here")
        self.assertContains(pending, "Complete and freeze", html=False)
        self.assertContains(pending, "disabled")

        quick_found = self.client.get(
            detail_url,
            {
                "item": self.item.pk,
                "classification": "FOUND",
                "location": expected_box.pk,
            },
        )
        self.assertEqual(
            quick_found.context["form"]["collateral_item"].value(), str(self.item.pk)
        )
        self.assertEqual(quick_found.context["form"]["classification"].value(), "FOUND")
        self.assertEqual(
            quick_found.context["form"]["observed_location"].value(),
            str(expected_box.pk),
        )

        observation = record_physical_verification_observation(
            session.pk,
            collateral_item_id=self.item.pk,
            classification="MISPLACED",
            observed_location_id=observed_box.pk,
            notes="Found in neighbouring box",
            actor=self.owner,
        )
        complete_physical_verification(session.pk, actor=self.owner)
        blocked = self.client.get(detail_url)
        self.assertContains(blocked, "Blocks operations")
        self.assertContains(blocked, "Resolve discrepancy")
        self.assertContains(blocked, "Alert Owner")

        alert_url = reverse(
            "loans:pawn_physical_verification_discrepancy_notice",
            args=[observation.pk],
        )
        self.client.post(alert_url)
        self.client.post(alert_url)
        notices = LoanOperationalNotice.objects.filter(
            source_verification_observation=observation
        )
        self.assertEqual(notices.count(), 1)
        evidence = self.client.get(detail_url)
        self.assertContains(evidence, "Owner alert QUEUED")
        self.assertContains(evidence, f"intent {notices.get().pk}")
        self.assertNotContains(evidence, "Retry failed alert")

        notice = notices.get()
        job = NotificationJob.objects.get(pk=notice.notification_job_id)
        job.status = NotificationJob.Status.FAILED
        job.failure_reason = "Pilot provider failure"
        job.attempt_count = 2
        job.last_attempt_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "failure_reason",
                "attempt_count",
                "last_attempt_at",
                "modified",
            ]
        )
        failed = self.client.get(detail_url)
        self.assertContains(failed, "Owner alert FAILED")
        self.assertContains(failed, "Attempts 2")
        self.assertContains(failed, "Pilot provider failure")
        self.assertContains(failed, "Retry failed alert")

    def _location(self, level, code, parent, capacity=None):
        return create_storage_location(
            workspace=self.tenant,
            level=level,
            code=code,
            name=code,
            parent=parent,
            capacity=capacity,
            actor=self.owner,
        )
