from django.apps import apps
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.girvi.models import GivenLoan

from .release_lifecycle import ReleaseCreateCommand, ReleaseLifecycleService


class BulkReleaseService:
    """Orchestrate multi-loan release preview and commit workflows."""

    COMMIT_POLICY_STRICT = "strict"
    COMMIT_POLICY_PARTIAL = "partial"
    DEFAULT_COMMIT_POLICY = COMMIT_POLICY_STRICT

    @staticmethod
    def parse_selected_ids(raw_ids):
        cleaned = []
        for value in raw_ids:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                cleaned.append(parsed)
        return list(dict.fromkeys(cleaned))

    @staticmethod
    def build_summary(loans):
        return {
            "total_loans": len(loans),
            "total_principal": sum(loan.get_loan_amount for loan in loans),
            "total_interest": sum(loan.interest_due() for loan in loans),
            "total_amount": sum(loan.total_due for loan in loans),
        }

    @classmethod
    def build_bulk_form(cls, raw_selected_ids=None):
        from ..forms import BulkReleaseForm

        selected_ids = cls.parse_selected_ids(raw_selected_ids or [])
        initial = {"date": timezone.now().strftime("%Y-%m-%dT%H:%M")}
        if selected_ids:
            initial["loans"] = GivenLoan.objects.filter(
                release__isnull=True, id__in=selected_ids
            ).values_list("id", flat=True)
        return BulkReleaseForm(initial=initial)

    @classmethod
    def build_preview_context(cls, loans, release_date, user=None):
        from ..forms import build_release_formset

        Release = apps.get_model("girvi", "Release")

        loans = list(loans)
        formset_initial_data = [
            {
                "loan": loan,
                "release_date": release_date,
                "released_by": loan.borrower,
                "release_amount": loan.total_due,
            }
            for loan in loans
        ]
        preview_formset_class = build_release_formset(extra=len(formset_initial_data))
        formset = preview_formset_class(
            queryset=Release.objects.none(), initial=formset_initial_data
        )
        return cls.build_review_context(
            formset,
            cls.build_summary(loans),
            commit_policy=cls.DEFAULT_COMMIT_POLICY,
            user=user,
        )

    @classmethod
    def bind_submit_formset(cls, post_data):
        from ..forms import ReleaseFormSet

        Release = apps.get_model("girvi", "Release")
        return ReleaseFormSet(post_data, queryset=Release.objects.none())

    @classmethod
    def extract_formset_loan_ids(cls, post_data):
        try:
            total_forms = int(post_data.get("form-TOTAL_FORMS", 0))
        except (TypeError, ValueError):
            return []

        loan_ids = []
        for index in range(total_forms):
            value = post_data.get(f"form-{index}-loan")
            if value:
                loan_ids.append(value)

        return cls.parse_selected_ids(loan_ids)

    @staticmethod
    def has_row_errors(formset):
        for form in formset.forms:
            delete_key = form.add_prefix("DELETE")
            if form.data.get(delete_key) in {True, "True", "true", "on", "1"}:
                continue
            if getattr(form, "cleaned_data", None) and form.cleaned_data.get("DELETE"):
                continue
            if form.errors:
                return True
        return False

    @classmethod
    def _resolve_form_preview_inputs(cls, form):
        loan = getattr(form, "loan_preview", None)
        release_date = None
        released_by = None

        cleaned_data = getattr(form, "cleaned_data", None) or {}
        if cleaned_data and not cleaned_data.get("DELETE"):
            loan = cleaned_data.get("loan") or loan
            release_date = cleaned_data.get("release_date")
            released_by = cleaned_data.get("released_by")
        else:
            initial = getattr(form, "initial", {}) or {}
            loan = initial.get("loan") or loan
            release_date = initial.get("release_date")
            released_by = initial.get("released_by")

            if getattr(form, "is_bound", False):
                form_data = getattr(form, "data", {})
                release_date = form_data.get(form.add_prefix("release_date")) or release_date
                released_by = form_data.get(form.add_prefix("released_by")) or released_by

        return loan, release_date, released_by

    @classmethod
    def _attach_release_previews(cls, formset, user=None):
        warning_count = 0
        blocker_count = 0

        for form in formset.forms:
            form.release_preview = None
            if not user:
                continue

            loan, release_date, released_by = cls._resolve_form_preview_inputs(form)
            if not loan:
                continue

            preview = ReleaseLifecycleService.preview(
                ReleaseCreateCommand(
                    loan=loan,
                    created_by=user,
                    release_date=release_date,
                    released_by=released_by,
                )
            )
            form.release_preview = preview

            if preview.errors:
                blocker_count += 1
            elif preview.warnings:
                warning_count += 1

        return warning_count, blocker_count

    @classmethod
    def build_review_context(
        cls,
        formset,
        summary,
        has_blocking_errors=False,
        commit_policy=None,
        user=None,
    ):
        resolved_policy = cls._normalize_commit_policy(commit_policy)
        preview_warning_count, preview_blocker_count = cls._attach_release_previews(
            formset, user=user
        )
        return {
            "formset": formset,
            "summary": summary,
            "has_row_errors": cls.has_row_errors(formset),
            "has_blocking_errors": has_blocking_errors,
            "has_preview_warnings": preview_warning_count > 0,
            "has_preview_blockers": preview_blocker_count > 0,
            "preview_warning_count": preview_warning_count,
            "preview_blocker_count": preview_blocker_count,
            "commit_policy": resolved_policy,
        }

    @classmethod
    def get_summary_for_post(cls, post_data):
        selected_loan_ids = cls.extract_formset_loan_ids(post_data)
        loans = list(
            GivenLoan.objects.filter(id__in=selected_loan_ids).select_related("borrower")
        )
        summary = cls.build_summary(loans) if loans else None
        return selected_loan_ids, summary

    @classmethod
    def commit_formset(cls, formset, user):
        return cls.commit_formset_with_policy(
            formset, user, commit_policy=cls.DEFAULT_COMMIT_POLICY
        )

    @classmethod
    def _normalize_commit_policy(cls, commit_policy):
        if commit_policy in {cls.COMMIT_POLICY_STRICT, cls.COMMIT_POLICY_PARTIAL}:
            return commit_policy
        return cls.DEFAULT_COMMIT_POLICY

    @classmethod
    def commit_formset_with_policy(cls, formset, user, commit_policy=None):
        commit_policy = cls._normalize_commit_policy(commit_policy)
        selected_loan_ids, summary = cls.get_summary_for_post(formset.data)

        if not formset.is_valid():
            return {
                "success": False,
                "commit_policy": commit_policy,
                **cls.build_review_context(
                    formset,
                    summary,
                    has_blocking_errors=bool(formset.non_form_errors()),
                    commit_policy=commit_policy,
                    user=user,
                ),
            }

        with transaction.atomic():
            locked_loans = GivenLoan.objects.select_for_update().filter(
                id__in=selected_loan_ids
            )
            released_ids = set(
                locked_loans.filter(release__isnull=False).values_list("id", flat=True)
            )

            if released_ids and commit_policy == cls.COMMIT_POLICY_STRICT:
                formset._non_form_errors = formset.error_class(
                    [
                        "Some selected loans were released by another process. "
                        "Please refresh and try again."
                    ]
                )
                return {
                    "success": False,
                    "commit_policy": commit_policy,
                    **cls.build_review_context(
                        formset,
                        summary,
                        has_blocking_errors=True,
                        commit_policy=commit_policy,
                        user=user,
                    ),
                }

            instances = []
            skipped_released_count = 0
            for form in formset.forms:
                if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                    continue

                loan = form.cleaned_data.get("loan")
                if (
                    loan
                    and loan.id in released_ids
                    and commit_policy == cls.COMMIT_POLICY_PARTIAL
                ):
                    skipped_released_count += 1
                    form.add_error(
                        "loan", "This loan was already released. Skipped in partial mode."
                    )
                    continue

                instances.append(
                    ReleaseLifecycleService.create_release(
                        loan=form.cleaned_data["loan"],
                        created_by=user,
                        release_date=form.cleaned_data["release_date"],
                        released_by=form.cleaned_data.get("released_by"),
                    )
                )

        if commit_policy == cls.COMMIT_POLICY_PARTIAL and skipped_released_count:
            if not instances:
                formset._non_form_errors = formset.error_class(
                    [
                        "All selected loans were stale at submit time. "
                        "No releases were created."
                    ]
                )
                return {
                    "success": False,
                    "commit_policy": commit_policy,
                    **cls.build_review_context(
                        formset,
                        summary,
                        has_blocking_errors=True,
                        commit_policy=commit_policy,
                        user=user,
                    ),
                }

            return {
                "success": True,
                "instances": instances,
                "commit_policy": commit_policy,
                "skipped_released_count": skipped_released_count,
            }

        return {
            "success": True,
            "instances": instances,
            "commit_policy": commit_policy,
            "skipped_released_count": 0,
        }
