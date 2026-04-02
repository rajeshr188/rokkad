from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction


class ReleaseLifecycleService:
    """Command-style release creation for GivenLoan lifecycle writes."""

    @staticmethod
    def create_release(*, loan, created_by, release_date, released_by=None):
        from apps.tenant_apps.girvi.flows import LoanFlow
        from apps.tenant_apps.girvi.payment_service import record_loan_release

        Release = apps.get_model("girvi", "Release")

        if not created_by:
            raise ValidationError("created_by is required for release creation.")

        with transaction.atomic():
            flow = LoanFlow(loan, created_by, created_by.profile.workspace)
            if not flow.deliver.can_proceed():
                raise ValidationError(
                    f"Loan {loan.loan_id} cannot be released in status {loan.status}."
                )

            release = Release(
                loan=loan,
                release_date=release_date,
                released_by=released_by,
                created_by=created_by,
            )
            release.save()

            flow.deliver(
                created_by=created_by,
                released_by=released_by,
                release_date=release_date,
            )
            record_loan_release(release, created_by=created_by)

            return release
