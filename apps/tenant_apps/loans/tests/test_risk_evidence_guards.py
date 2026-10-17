"""Adversarial risk DML under forced RLS, plus populated owner-only upgrades."""

from contextlib import contextmanager
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, DatabaseError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import historical_migration_database
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.collateral_reappraisal import (
    record_collateral_reappraisal,
)
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures

upgrade = import_module("apps.tenant_apps.loans.migrations.0072_risk_evidence_guards")


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class RiskEvidenceDatabaseTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username=uuid4().hex)
        owner = Role.objects.get_or_create(name="Owner")[0]
        self.workspace = Company.objects.create(
            name="Risk guards",
            schema_name=uuid4().hex,
            owner=self.actor,
            creator=self.actor,
        )
        self.foreign = Company.objects.create(
            name="Foreign risk guards",
            schema_name=uuid4().hex,
            owner=self.actor,
            creator=self.actor,
        )
        self.memberships = [
            Membership.objects.create(company=w, user=self.actor, role=owner)
            for w in (self.workspace, self.foreign)
        ]
        self.a = self.position(self.workspace)
        self.b = self.position(self.workspace)
        self.c = self.position(self.foreign)
        with workspace_context(self.foreign.pk):
            self.unassessed = self.bare_loan(self.c)
        role = "risk_guard_" + uuid4().hex
        self.role = connection.ops.quote_name(role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {self.role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {self.role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {self.role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {self.role}"
            )
        self.addCleanup(self.drop_role)

    def drop_role(self):
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(f"DROP OWNED BY {self.role}")
            cursor.execute(f"DROP ROLE {self.role}")

    def position(self, workspace):
        holder = SimpleNamespace(tenant=workspace, actor=self.actor)
        with workspace_context(workspace.pk):
            create_sequence = m.LoanNumberSequence.objects.create
            create_policy = m.LoanMonitoringPolicy.objects.create

            def distinct_sequence(**values):
                return create_sequence(
                    **{**values, "prefix": "R" + uuid4().hex[:8] + "-"}
                )

            def standing_policy(**values):
                existing = m.LoanMonitoringPolicy.objects.filter(
                    workspace=workspace, license__isnull=True
                ).first()
                return existing if existing is not None else create_policy(**values)

            with (
                patch.object(
                    m.LoanNumberSequence.objects,
                    "create",
                    side_effect=distinct_sequence,
                ),
                patch.object(
                    m.LoanMonitoringPolicy.objects,
                    "create",
                    side_effect=standing_policy,
                ),
            ):
                fixtures.CollateralReappraisalTests.make_loan(
                    holder, method="LATEST_APPRAISAL"
                )
            record_collateral_reappraisal(
                loan_id=holder.loan.pk,
                item_id=holder.item.pk,
                actor=self.actor,
                appraised_value="1400",
                method="PHYSICAL_INSPECTION",
                evidence_reference="Synthetic inspection",
                review_notes="Reference-guard fixture",
                expected_version=1,
            )
            holder.snapshot = refresh_loan_risk_snapshot(
                holder.loan.pk, as_of_date=holder.today
            )
            holder.alert = m.LoanRiskAlert.objects.get(loan=holder.loan, status="OPEN")
            holder.event = holder.alert.source_event
        return holder

    def bare_loan(self, holder):
        return m.PawnLoan.objects.create(
            workspace=holder.tenant,
            license=holder.loan.license,
            series=holder.loan.series,
            borrower=holder.loan.borrower,
            product_version=holder.loan.product_version,
            loan_number=uuid4().hex,
            principal_amount=1000,
            monthly_interest_rate=2,
            tenure_months=12,
            loan_date=holder.today,
        )

    @contextmanager
    def runtime(self, workspace=None):
        with workspace_context((workspace or self.workspace).pk):
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {self.role}")
                cursor.execute(
                    "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
                )
                self.assertEqual(cursor.fetchone(), (False, False))
            yield

    def rejected(self, action, *, constraint=None, message=None):
        with self.assertRaises(DatabaseError) as caught, transaction.atomic():
            action()
        if constraint:
            self.assertEqual(
                caught.exception.__cause__.diag.constraint_name, constraint
            )
        if message:
            self.assertIn(message, str(caught.exception))

    def event(self, **changes):
        values = dict(
            workspace=self.workspace,
            loan=self.a.loan,
            snapshot=self.a.snapshot,
            event_type="TEST_REFERENCE",
            as_of_date=self.a.today,
            trigger_key=uuid4().hex,
        )
        values.update(changes)
        return m.LoanRiskEvent.objects.create(**values)

    def alert(self, **changes):
        values = dict(
            workspace=self.workspace,
            loan=self.a.loan,
            source_event=self.a.event,
            alert_kind="MATURITY",
            severity="HIGH",
            message="Synthetic guard fixture",
            recommended_action="Review",
        )
        values.update(changes)
        return m.LoanRiskAlert.objects.create(**values)

    def notice(self, **changes):
        now = timezone.now()
        values = dict(
            workspace=self.workspace,
            loan=self.a.loan,
            source_risk_alert=self.a.alert,
            source_risk_event=self.a.event,
            notice_kind="OVERDUE_REMINDER",
            channel="EMAIL",
            request_key=uuid4().hex,
            scheduled_for=now,
            created_at=now,
            updated_at=now,
            recipient_name="Test borrower",
            recipient_email="guard@example.invalid",
            notification_template_id=1,
            notification_template_version=1,
        )
        values.update(changes)
        notice = m.PawnLoanNotice(**values)
        # Adversarial DML bypasses clean()/save() and auto_now processing.
        notice.save_base(raw=True, force_insert=True)
        return notice

    def test_events_reject_bulk_raw_noop_update_and_delete(self):
        with self.runtime():
            event = self.event()
            actions = (
                lambda: m.LoanRiskEvent.objects.filter(pk=event.pk).update(
                    metadata={"changed": True}
                ),
                lambda: m.LoanRiskEvent.objects.bulk_update(
                    [m.LoanRiskEvent(pk=event.pk, event_type="CHANGED")], ["event_type"]
                ),
                lambda: self.sql(
                    "UPDATE loans_loanriskevent SET event_type=event_type WHERE id=%s",
                    [event.pk],
                ),
                lambda: self.sql(
                    "DELETE FROM loans_loanriskevent WHERE id=%s", [event.pk]
                ),
                lambda: m.LoanRiskEvent.objects.filter(pk=event.pk).delete(),
            )
            for action in actions:
                with self.subTest(action=action):
                    self.rejected(action, message="Risk events are immutable")
            event.refresh_from_db()
            self.assertEqual(event.event_type, "TEST_REFERENCE")
            self.assertEqual(event.metadata, {})

    def sql(self, query, parameters=()):
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            return cursor.rowcount

    def test_composite_references_reject_foreign_workspace_and_same_workspace_wrong_loan(
        self,
    ):
        with self.runtime():
            self.rejected(
                lambda: m.LoanRiskSnapshot.objects.create(
                    workspace=self.workspace,
                    loan=self.unassessed,
                    as_of_date=self.a.today,
                    status="ERROR",
                ),
                constraint="loans_risk_snapshot_loan_scope_fk",
            )
            for wrong in (self.b, self.c):
                with self.subTest(loan=wrong.loan.pk):
                    self.rejected(
                        lambda: self.event(snapshot=wrong.snapshot),
                        constraint="loans_risk_event_snapshot_scope_fk",
                    )
                    self.rejected(
                        lambda: self.alert(source_event=wrong.event),
                        constraint="loans_risk_alert_source_scope_fk",
                    )
                    self.rejected(
                        lambda: m.LoanRiskAlert.objects.filter(
                            pk=self.a.alert.pk
                        ).update(resolved_by_event=wrong.event),
                        constraint="loans_risk_alert_recovery_scope_fk",
                    )
                    self.rejected(
                        lambda: self.notice(
                            source_risk_alert=wrong.alert, source_risk_event=wrong.event
                        ),
                        constraint="loans_notice_risk_binding_fk",
                    )
            self.rejected(
                lambda: self.notice(source_risk_event=self.event()),
                constraint="loans_notice_risk_binding_fk",
            )
            for changes in ({"source_risk_event": None}, {"source_risk_alert": None}):
                self.rejected(
                    lambda: self.notice(**changes),
                    constraint="loans_notice_risk_pair_complete",
                )

    def test_projection_and_alert_anchors_cannot_be_reassigned(self):
        with self.runtime():
            for changes in (
                {"loan": self.b.loan},
                {"workspace": self.foreign},
                {"id": 999999999},
            ):
                self.rejected(
                    lambda: m.LoanRiskSnapshot.objects.filter(
                        pk=self.a.snapshot.pk
                    ).update(**changes),
                    message="Risk snapshot identity cannot be reassigned",
                )
            second = self.event()
            for changes in (
                {"source_event": second},
                {"loan": self.b.loan},
                {"workspace": self.foreign},
                {"alert_kind": "MATURITY"},
            ):
                self.rejected(
                    lambda: m.LoanRiskAlert.objects.filter(pk=self.a.alert.pk).update(
                        **changes
                    ),
                    message="Risk alert source identity cannot be reassigned",
                )
            notice = self.notice()
            second_alert = self.alert(source_event=second)
            self.rejected(
                lambda: m.PawnLoanNotice.objects.filter(pk=notice.pk).update(
                    source_risk_alert=second_alert, source_risk_event=second
                ),
                message="Notice risk source identity cannot be reassigned",
            )
            self.rejected(
                lambda: m.PawnLoanNotice.objects.filter(pk=notice.pk).update(
                    source_risk_alert=None, source_risk_event=None
                ),
                message="Notice risk source identity cannot be reassigned",
            )

    def test_normal_reassessment_escalation_recovery_and_notice_routing_remain_mutable(
        self,
    ):
        with self.runtime():
            financial = list(self.a.loan.loan_events.values())
            notice = self.notice()
            source = self.a.alert.source_event_id
            m.LoanRiskSnapshot.objects.filter(pk=self.a.snapshot.pk).update(
                status="STALE"
            )
            for value, version in (("1000", 2), ("4000", 3)):
                record_collateral_reappraisal(
                    loan_id=self.a.loan.pk,
                    item_id=self.a.item.pk,
                    actor=self.actor,
                    appraised_value=value,
                    method="PHYSICAL_INSPECTION",
                    evidence_reference="Synthetic later inspection",
                    review_notes="Known risk change",
                    expected_version=version,
                )
                refresh_loan_risk_snapshot(self.a.loan.pk, as_of_date=self.a.today)
                self.a.alert.refresh_from_db()
                if value == "1000":
                    self.assertEqual(
                        (self.a.alert.status, self.a.alert.severity),
                        ("OPEN", "CRITICAL"),
                    )
            self.assertEqual(self.a.alert.status, "RESOLVED")
            self.assertEqual(self.a.alert.source_event_id, source)
            self.assertEqual(
                self.a.alert.resolved_by_event.event_type, "LTV_CRITICAL_CURED"
            )
            m.PawnLoanNotice.objects.filter(pk=notice.pk).update(notification_job_id=42)
            notice.refresh_from_db()
            self.assertEqual(notice.notification_job_id, 42)
            self.assertEqual(list(self.a.loan.loan_events.values()), financial)

    def test_rls_runtime_role_and_owner_only_preflight(self):
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {self.role}")
        try:
            for model in (
                m.LoanRiskSnapshot,
                m.LoanRiskEvent,
                m.LoanRiskAlert,
                m.PawnLoanNotice,
            ):
                self.assertEqual(model.objects.count(), 0)
            self.rejected(
                lambda: m.LoanRiskSnapshot.objects.create(
                    workspace=self.foreign,
                    loan=self.unassessed,
                    as_of_date=self.a.today,
                    status="ERROR",
                ),
                message="row-level security",
            )
            with self.assertRaisesMessage(CommandError, "owner migration role"):
                call_command("check_risk_evidence", stdout=StringIO())
            with workspace_context(self.workspace.pk):
                self.assertFalse(
                    m.LoanRiskSnapshot.objects.filter(pk=self.c.snapshot.pk).exists()
                )
                self.assertFalse(
                    m.LoanRiskEvent.objects.filter(pk=self.c.event.pk).exists()
                )
                self.assertEqual(
                    self.sql(
                        "UPDATE loans_loanriskevent SET event_type='CHANGED' WHERE id=%s",
                        [self.c.event.pk],
                    ),
                    0,
                )
                self.rejected(
                    lambda: self.sql(
                        "DROP TRIGGER loans_risk_event_immutable_guard ON loans_loanriskevent"
                    )
                )
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_table_privilege(current_user,'loans_loanriskevent','TRUNCATE')"
                    )
                    self.assertFalse(cursor.fetchone()[0])
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

    def test_owner_preflight_is_read_only(self):
        with workspace_context(self.workspace.pk):
            # The composite reference also prevents an owner from moving a parent
            # loan out of its snapshot's Workspace, even with RLS bypass.
            loan = self.bare_loan(self.a)
            m.LoanRiskSnapshot.objects.create(
                workspace=self.workspace,
                loan=loan,
                as_of_date=self.a.today,
                status="ERROR",
            )
            self.rejected(
                lambda: m.PawnLoan.objects.filter(pk=loan.pk).update(
                    workspace=self.foreign
                ),
                message="Loan identity cannot move Workspaces",
            )
            before = list(m.LoanRiskEvent.objects.order_by("pk").values())
        output = StringIO()
        call_command("check_risk_evidence", stdout=output)
        self.assertIn('"EVENT_SNAPSHOT_SCOPE": 0', output.getvalue())
        self.assertIn("preflight passed", output.getvalue())
        with workspace_context(self.workspace.pk):
            self.assertEqual(
                list(m.LoanRiskEvent.objects.order_by("pk").values()), before
            )

    def historical_sources(self):
        with workspace_context(self.workspace.pk):
            loans = [self.bare_loan(self.a), self.bare_loan(self.b)]
            alerts = []
            for loan in loans:
                snapshot = m.LoanRiskSnapshot.objects.create(
                    workspace=self.workspace,
                    loan=loan,
                    as_of_date=self.a.today,
                    status="ERROR",
                    error_message="Preserved test failure",
                )
                event = self.event(
                    loan=loan, snapshot=snapshot, event_type="ASSESSMENT_ERROR_ENTERED"
                )
                alerts.append(
                    self.alert(
                        loan=loan, source_event=event, alert_kind="ASSESSMENT_FAILURE"
                    )
                )
            notice = self.notice(
                loan=loans[0],
                source_risk_alert=alerts[0],
                source_risk_event=alerts[0].source_event,
            )
            # Legacy resolutions without a cure link are retained, never fabricated.
            m.LoanRiskAlert.objects.filter(pk=alerts[1].pk).update(
                status="RESOLVED", resolved_at=timezone.now()
            )
        return [*self.memberships, *alerts, notice, self.unassessed], loans, alerts

    def test_populated_upgrade_preserves_evidence_and_legacy_missing_cure(self):
        sources, _, _ = self.historical_sources()
        before, after = [("loans", "0068_compact_closed_position_evidence")], [
            ("loans", "0072_risk_evidence_guards")
        ]
        with historical_migration_database(self, before, sources) as (target, old_apps):
            names = (
                "LoanRiskSnapshot",
                "LoanRiskEvent",
                "LoanRiskAlert",
                "PawnLoanNotice",
            )
            retained = {
                name: list(
                    old_apps.get_model("loans", name)
                    .objects.using(target.alias)
                    .order_by("pk")
                    .values()
                )
                for name in names
            }
            report = upgrade.read_preflight(target)
            self.assertFalse(any(report["violations"].values()))
            self.assertEqual(report["legacy_resolved_without_event"], 1)
            executor = MigrationExecutor(target)
            executor.migrate(after)
            new_apps = executor.loader.project_state(after).apps
            for name in names:
                self.assertEqual(
                    list(
                        new_apps.get_model("loans", name)
                        .objects.using(target.alias)
                        .order_by("pk")
                        .values()
                    ),
                    retained[name],
                )
            with target.cursor() as cursor:
                cursor.execute("UPDATE loans_loanrisksnapshot SET status='ERROR'")
                with (
                    self.assertRaises(DatabaseError),
                    transaction.atomic(using=target.alias),
                ):
                    cursor.execute("UPDATE loans_loanriskevent SET metadata='{}'")

    def test_populated_upgrade_refuses_invalid_links_without_repair(self):
        sources, loans, alerts = self.historical_sources()
        before, after = [("loans", "0068_compact_closed_position_evidence")], [
            ("loans", "0072_risk_evidence_guards")
        ]
        with historical_migration_database(self, before, sources) as (target, old_apps):
            snapshot = old_apps.get_model("loans", "LoanRiskSnapshot")
            event = old_apps.get_model("loans", "LoanRiskEvent")
            alert = old_apps.get_model("loans", "LoanRiskAlert")
            notice = old_apps.get_model("loans", "PawnLoanNotice")
            a, b = [alert.objects.using(target.alias).get(pk=row.pk) for row in alerts]
            source_a = event.objects.using(target.alias).get(pk=a.source_event_id)
            source_b = event.objects.using(target.alias).get(pk=b.source_event_id)
            snapshot.objects.using(target.alias).create(
                workspace_id=self.workspace.pk,
                loan_id=self.unassessed.pk,
                as_of_date=self.a.today,
                status="ERROR",
            )
            event.objects.using(target.alias).create(
                workspace_id=self.workspace.pk,
                loan_id=loans[1].pk,
                snapshot_id=source_a.snapshot_id,
                event_type="INVALID_SCOPE",
                as_of_date=self.a.today,
                trigger_key=uuid4().hex,
            )
            alert.objects.using(target.alias).create(
                workspace_id=self.workspace.pk,
                loan_id=loans[1].pk,
                source_event_id=source_a.pk,
                alert_kind="MATURITY",
                severity="HIGH",
            )
            alert.objects.using(target.alias).filter(pk=a.pk).update(
                resolved_by_event_id=source_b.pk
            )
            notice.objects.using(target.alias).create(
                workspace_id=self.workspace.pk,
                loan_id=loans[1].pk,
                source_risk_alert_id=a.pk,
                source_risk_event_id=source_a.pk,
                notice_kind="MATURITY_NOTICE",
                channel="EMAIL",
                request_key=uuid4().hex,
                scheduled_for=timezone.now(),
            )
            report = upgrade.read_preflight(target)
            self.assertEqual(
                report["violations"], {name: 1 for name, _ in upgrade.REFERENCE_CHECKS}
            )
            retained = list(event.objects.using(target.alias).order_by("pk").values())
            with self.assertRaisesMessage(
                RuntimeError, "explicit review before migration"
            ):
                MigrationExecutor(target).migrate(after)
            self.assertEqual(
                list(event.objects.using(target.alias).order_by("pk").values()),
                retained,
            )
            with target.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM django_migrations WHERE app='loans' AND name='0072_risk_evidence_guards'"
                )
                self.assertEqual(cursor.fetchone()[0], 0)
                cursor.execute(
                    "SELECT count(*) FROM pg_trigger WHERE tgname='loans_risk_event_immutable_guard'"
                )
                self.assertEqual(cursor.fetchone()[0], 0)
