from types import SimpleNamespace
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.storagebox_workflow import (
    StorageBoxWorkflowService,
)


class StorageBoxWorkflowServiceTests(SimpleTestCase):
    def test_assign_item_range_sets_start_and_end_items(self):
        start_item = SimpleNamespace(id=10)
        end_item = SimpleNamespace(id=20)

        start_loan = SimpleNamespace(
            loanitems=SimpleNamespace(
                filter=MagicMock(return_value=SimpleNamespace(first=MagicMock(return_value=start_item)))
            )
        )
        end_loan = SimpleNamespace(
            loanitems=SimpleNamespace(
                filter=MagicMock(return_value=SimpleNamespace(last=MagicMock(return_value=end_item)))
            )
        )
        instance = SimpleNamespace(item_type="Gold", start_item=None, end_item=None)

        result = StorageBoxWorkflowService.assign_item_range(
            instance,
            start_loan=start_loan,
            end_loan=end_loan,
        )

        self.assertIs(result.start_item, start_item)
        self.assertIs(result.end_item, end_item)

    def test_assign_item_range_raises_when_items_missing(self):
        start_loan = SimpleNamespace(
            loanitems=SimpleNamespace(
                filter=MagicMock(return_value=SimpleNamespace(first=MagicMock(return_value=None)))
            )
        )
        end_loan = SimpleNamespace(
            loanitems=SimpleNamespace(
                filter=MagicMock(return_value=SimpleNamespace(last=MagicMock(return_value=None)))
            )
        )
        instance = SimpleNamespace(item_type="Silver", start_item=None, end_item=None)

        with self.assertRaises(ValidationError):
            StorageBoxWorkflowService.assign_item_range(
                instance,
                start_loan=start_loan,
                end_loan=end_loan,
            )

    def test_save_from_form_assigns_range_and_saves(self):
        instance = SimpleNamespace(item_type="Gold", save=MagicMock())
        form = SimpleNamespace(
            cleaned_data={
                "start_item_id": SimpleNamespace(
                    loanitems=SimpleNamespace(
                        filter=MagicMock(
                            return_value=SimpleNamespace(
                                first=MagicMock(return_value=SimpleNamespace(id=1))
                            )
                        )
                    )
                ),
                "end_item_id": SimpleNamespace(
                    loanitems=SimpleNamespace(
                        filter=MagicMock(
                            return_value=SimpleNamespace(
                                last=MagicMock(return_value=SimpleNamespace(id=2))
                            )
                        )
                    )
                ),
            },
            save=MagicMock(return_value=instance),
        )

        result = StorageBoxWorkflowService.save_from_form(form)

        self.assertIs(result, instance)
        form.save.assert_called_once_with(commit=False)
        instance.save.assert_called_once_with()
