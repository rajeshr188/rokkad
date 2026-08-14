"""Workflow helpers for storage box create/update orchestration."""

from django.core.exceptions import ValidationError


class StorageBoxWorkflowService:
    """Keep storage-box views thin by centralizing range-assignment behavior."""

    @staticmethod
    def assign_item_range(instance, *, start_loan, end_loan):
        instance.start_item = start_loan.loanitems.filter(itemtype=instance.item_type).first()
        instance.end_item = end_loan.loanitems.filter(itemtype=instance.item_type).last()

        if not instance.start_item or not instance.end_item:
            raise ValidationError(
                "Selected loans must contain items matching the storage box item type."
            )

        return instance

    @classmethod
    def save_from_form(cls, form, *, commit=True):
        instance = form.save(commit=False)
        start_loan = form.cleaned_data["start_item_id"]
        end_loan = form.cleaned_data["end_item_id"]
        cls.assign_item_range(instance, start_loan=start_loan, end_loan=end_loan)
        if commit:
            instance.save()
        return instance
