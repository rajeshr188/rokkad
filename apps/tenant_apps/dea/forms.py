from crispy_forms.helper import FormHelper
from crispy_forms.layout import Button, Submit
from django import forms
from django.urls import reverse_lazy
from django.utils import timezone
from django_select2 import forms as s2forms
from djmoney.forms import MoneyField

from .models import (
    Account,
    AccountingPeriod,
    AccountStatement,
    AccountTransaction,
    JournalEntry,
    Ledger,
    LedgerStatement,
    LedgerTransaction,
    Voucher,
)


class AccountWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "contact__firstname__icontains",
        "contact__lastname__icontains",
        "contact__relatedas__icontains",
        "contact__relatedto__icontains",
        "contact__contactno__phone_number__icontains",
    ]


class LedgerWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "name__icontains",
        "AccountType__AccountType__icontains",
        "parent__name__icontains",
    ]
    help_text = "Ledger"


class JournalEntryWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "desc__icontains",
    ]


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = "__all__"


class AccountStatementForm(forms.ModelForm):
    class Meta:
        model = AccountStatement
        fields = ("AccountNo", "ClosingBalance", "TotalCredit", "TotalDebit")


class LedgerForm(forms.ModelForm):
    class Meta:
        model = Ledger
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(LedgerForm, self).__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        self.fields["parent"].queryset = Ledger.objects.exclude(pk=self.instance.pk)
        self.helper = FormHelper()
        if instance:
            self.helper.attrs = {
                "hx-post": reverse_lazy("dea_ledger_update", kwargs={"pk": instance.pk})
            }
            cancel_url = reverse_lazy("dea_ledger_detail", kwargs={"pk": instance.id})
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-get": cancel_url,
                    "hx-target": "closest form",
                    "hx-swap": "outerHTML",
                },
            )
        else:
            self.helper.attrs = {"hx-post": reverse_lazy("dea_ledger_create")}
            cancel_url = reverse_lazy("dea_ledger_list")
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-on": 'click: this.closest("form").remove()',
                },
            )
        self.helper.add_input(Submit("submit", "Save", css_class="btn btn-success"))
        self.helper.add_input(cancel_button)


class LedgerStatementForm(forms.ModelForm):
    class Meta:
        model = LedgerStatement
        fields = ("ledgerno", "ClosingBalance")


class LedgerTransactionForm(forms.ModelForm):
    ledgerno = forms.ModelChoiceField(
        queryset=Ledger.objects.all(),
        widget=LedgerWidget(attrs={"data-placeholder": "Select credit ledger..."}),
        help_text="Credit Ledger",
    )
    ledgerno_dr = forms.ModelChoiceField(
        queryset=Ledger.objects.all(),
        widget=LedgerWidget(attrs={"data-placeholder": "Select debit ledger..."}),
        help_text="Debit Ledger",
    )
    amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR")

    class Meta:
        model = LedgerTransaction
        fields = ("ledgerno", "ledgerno_dr", "amount")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data["ledgerno"] == cleaned_data["ledgerno_dr"]:
            raise forms.ValidationError("Ledger No and Ledger No Dr cannot be same")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        # lt = kwargs.pop("lt")
        journalentry_id = kwargs.pop("journalentry_id", None)
        instance = kwargs.get("instance")
        super(LedgerTransactionForm, self).__init__(*args, **kwargs)
        # self.fields["ledgerno_dr"].queryset = Ledger.objects.exclude(
        #     pk=self.instance.ledgerno.pk
        # )
        self.helper = FormHelper()

        if instance:
            self.helper.attrs = {
                "hx-post": reverse_lazy(
                    "dea_ledgertransaction_create",
                    kwargs={"pk": instance.journal_entry.pk},
                )
            }
            cancel_url = reverse_lazy(
                "dea_ledgertransaction_detail", kwargs={"pk": instance.id}
            )
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-get": cancel_url,
                    "hx-target": "closest li",
                    "hx-swap": "outerHTML",
                },
            )
        else:
            self.helper.attrs = {
                "hx-post": reverse_lazy(
                    "dea_ledgertransaction_create", kwargs={"pk": journalentry_id}
                )
            }
            cancel_url = reverse_lazy("dea_ledgertransaction_list")
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-on": 'click: this.closest("form").remove()',
                },
            )
        self.helper.add_input(cancel_button)
        self.helper.add_input(Submit("submit", "Save", css_class="btn btn-success"))


class AccountTransactionForm(forms.ModelForm):
    Account = forms.ModelChoiceField(
        queryset=Account.objects.all(),
        widget=AccountWidget(attrs={"data-placeholder": "Select an account..."}),
    )
    ledgerno = forms.ModelChoiceField(
        queryset=Ledger.objects.all(),
        widget=LedgerWidget(attrs={"data-placeholder": "Select a ledger..."}),
    )

    amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR")

    class Meta:
        model = AccountTransaction
        fields = ("ledgerno", "Account", "XactTypeCode", "XactTypeCode_ext", "amount")

    def __init__(self, *args, **kwargs):
        # lt = kwargs.pop("lt")
        journalentry_id = kwargs.pop("journalentry_id", None)
        instance = kwargs.get("instance")
        super(AccountTransactionForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        if instance:
            self.helper.attrs = {
                "hx-post": reverse_lazy(
                    "dea_accounttransaction_create",
                    kwargs={"pk": instance.journal_entry.pk},
                )
            }
            cancel_url = reverse_lazy(
                "dea_accounttransaction_detail", kwargs={"pk": instance.id}
            )
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-get": cancel_url,
                    "hx-target": "closest li",
                    "hx-swap": "outerHTML",
                },
            )
        else:
            self.helper.attrs = {
                "hx-post": reverse_lazy(
                    "dea_accounttransaction_create", kwargs={"pk": journalentry_id}
                )
            }
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-on": 'click: this.closest("form").remove()',
                },
            )
        self.helper.add_input(cancel_button)
        self.helper.add_input(Submit("submit", "Save", css_class="btn btn-success"))


class JournalEntryForm(forms.ModelForm):
    desc = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = JournalEntry
        fields = ("desc",)


# Accounting Period Forms
class AccountingPeriodForm(forms.ModelForm):
    """
    Form for creating and updating accounting periods
    """

    class Meta:
        model = AccountingPeriod
        fields = ("name", "start_date", "end_date", "notes")
        widgets = {
            "start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "end_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., Jan 2024, Q1 2024",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit("submit", "Save Period", css_class="btn btn-primary")
        )
        self.helper.add_input(
            Button(
                "cancel",
                "Cancel",
                css_class="btn btn-secondary",
                onclick="window.history.back()",
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if end_date <= start_date:
                raise forms.ValidationError("End date must be after start date")

            # Check for overlapping periods (excluding current instance in edit)
            overlapping = AccountingPeriod.objects.filter(
                start_date__lte=end_date, end_date__gte=start_date
            )
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            if overlapping.exists():
                raise forms.ValidationError(
                    f"This period overlaps with: {', '.join(str(p) for p in overlapping)}"
                )

        return cleaned_data


class PeriodAdjustmentForm(forms.Form):
    """Structured form for posting period-end adjustments before closing."""

    ADJUSTMENT_TYPE_CHOICES = [
        ("ACCRUAL", "Accrual"),
        ("PREPAID_EXPENSE", "Prepaid expense adjustment"),
        ("DEPRECIATION", "Depreciation"),
        ("INTEREST_ACCRUAL", "Interest accrual"),
        ("CUSTOM", "Custom adjustment"),
    ]

    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Choose the kind of month-end or year-end adjustment to post.",
    )
    effective_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text="This usually matches the period end date.",
    )
    debit_ledger = forms.ModelChoiceField(
        queryset=Ledger.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Debit ledger",
    )
    credit_ledger = forms.ModelChoiceField(
        queryset=Ledger.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Credit ledger",
    )
    amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR")
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-control",
                "placeholder": "Explain why this adjustment is needed for the period close...",
            }
        ),
        help_text="This note appears in the posted journal entry and review history.",
    )
    auto_reverse_next_period = forms.BooleanField(
        required=False,
        label="Flag for next-period reversal",
        help_text="Planning aid only for now; automatic reversal will be a future enhancement.",
    )

    def __init__(self, *args, period=None, **kwargs):
        self.period = period
        super().__init__(*args, **kwargs)
        ledger_queryset = Ledger.objects.select_related("AccountType").order_by("name")
        self.fields["debit_ledger"].queryset = ledger_queryset
        self.fields["credit_ledger"].queryset = ledger_queryset
        if period is not None:
            self.fields["effective_date"].initial = period.end_date

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit("submit", "Post Adjustment", css_class="btn btn-primary")
        )
        cancel_target = (
            reverse_lazy("dea_period_close", kwargs={"pk": period.pk})
            if period is not None
            else "javascript:history.back()"
        )
        self.helper.add_input(
            Button(
                "cancel",
                "Back to Close Checklist",
                css_class="btn btn-secondary",
                onclick=f"window.location.href='{cancel_target}'",
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        debit_ledger = cleaned_data.get("debit_ledger")
        credit_ledger = cleaned_data.get("credit_ledger")
        if debit_ledger and credit_ledger and debit_ledger == credit_ledger:
            raise forms.ValidationError("Debit and credit ledgers must be different.")
        return cleaned_data


class PeriodCloseForm(forms.Form):
    """
    Form for closing an accounting period with confirmation
    """

    review_adjustments = forms.BooleanField(
        label="I have reviewed or posted the required pre-close adjustments (accruals, prepaids, depreciation, and interest).",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    review_unposted_items = forms.BooleanField(
        label="I have reviewed all draft or unposted vouchers for this period.",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    review_carry_forward = forms.BooleanField(
        label="I understand income and expense balances will reset, while balance-sheet balances carry forward.",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    notes = forms.CharField(
        label="Closing Notes",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-control",
                "placeholder": "Enter any notes about this period close (optional)...",
            }
        ),
        help_text="Optional notes about the period closing process",
    )

    confirm = forms.BooleanField(
        label="I confirm that I want to close this accounting period",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="This action will close all revenue and expense accounts to retained earnings",
    )

    def __init__(self, *args, draft_vouchers_count=0, **kwargs):
        self.draft_vouchers_count = draft_vouchers_count
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit("submit", "Close Period", css_class="btn btn-danger")
        )
        self.helper.add_input(
            Button(
                "cancel",
                "Cancel",
                css_class="btn btn-secondary",
                onclick="window.history.back()",
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        if self.draft_vouchers_count:
            raise forms.ValidationError(
                f"This period still has {self.draft_vouchers_count} draft voucher(s). "
                "Post or reverse them before closing."
            )
        return cleaned_data


class PeriodFilterForm(forms.Form):
    """
    Form for filtering accounting periods list
    """

    STATUS_CHOICES = [("", "All Statuses")] + list(
        AccountingPeriod.PeriodStatus.choices
    )

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    start_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    start_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )


# Opening Balance Forms


class OpeningBalanceForm(forms.Form):
    """
    Form for entering opening balances for a specific accounting period
    """

    period = forms.ModelChoiceField(
        queryset=AccountingPeriod.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Accounting Period",
        help_text="Select the period to set opening balances for",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(Submit("submit", "Continue", css_class="btn btn-primary"))


class LedgerOpeningBalanceForm(forms.ModelForm):
    """
    Form for entering opening balance for a single ledger
    """

    class Meta:
        model = LedgerStatement
        fields = ("ClosingBalance",)
        widgets = {
            "ClosingBalance": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            )
        }
        labels = {"ClosingBalance": "Opening Balance"}


class AccountOpeningBalanceForm(forms.ModelForm):
    """
    Form for entering opening balance for a single account
    """

    class Meta:
        model = AccountStatement
        fields = ("ClosingBalance",)
        widgets = {
            "ClosingBalance": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"}
            )
        }
        labels = {"ClosingBalance": "Opening Balance"}


# Formsets for bulk opening balance entry
from django.forms import modelformset_factory, inlineformset_factory

LedgerOpeningBalanceFormSet = modelformset_factory(
    LedgerStatement, form=LedgerOpeningBalanceForm, extra=0, fields=("ClosingBalance",)
)

AccountOpeningBalanceFormSet = modelformset_factory(
    AccountStatement,
    form=AccountOpeningBalanceForm,
    extra=0,
    fields=("ClosingBalance",),
)


# ============================================================================
# VOUCHER FORMS
# ============================================================================


class VoucherForm(forms.ModelForm):
    """
    Form for creating and editing vouchers.

    Features:
    - Auto-generated voucher number
    - Date picker
    - Voucher type selection
    - Optional reference to business document
    - Narration/description
    """

    class Meta:
        model = Voucher
        fields = [
            "voucher_no",
            "voucher_type",
            "voucher_date",
            "narration",
            "doc_content_type",
            "doc_object_id",
        ]
        widgets = {
            "voucher_no": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Auto-generated",
                    "readonly": True,
                }
            ),
            "voucher_type": forms.Select(
                attrs={
                    "class": "form-select",
                    "data-placeholder": "Select voucher type...",
                }
            ),
            "voucher_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "narration": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Description of the transaction...",
                }
            ),
            "doc_content_type": forms.HiddenInput(),
            "doc_object_id": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["voucher_type"].required = True
        self.fields["voucher_date"].required = True
        self.fields["narration"].required = False
        self.fields["doc_content_type"].required = False
        self.fields["doc_object_id"].required = False


class VoucherLineItemForm(forms.Form):
    """
    Form for adding a line item (debit/credit entry) to a voucher.

    Used in inline editing with HTMX.
    """

    SIDE_CHOICES = [
        ("DEBIT", "Debit (DR)"),
        ("CREDIT", "Credit (CR)"),
    ]

    ledger = forms.ModelChoiceField(
        queryset=Ledger.objects.all(),
        widget=LedgerWidget(),
        label="GL Account",
        help_text="Select the general ledger account",
    )
    account = forms.ModelChoiceField(
        queryset=Account.objects.all(),
        widget=AccountWidget(),
        label="Account (Optional)",
        help_text="Customer/Vendor account (optional)",
        required=False,
    )
    side = forms.ChoiceField(
        choices=SIDE_CHOICES,
        widget=forms.RadioSelect(
            attrs={
                "class": "form-check-input",
            }
        ),
        label="Debit or Credit",
    )
    amount = MoneyField(
        max_digits=13,
        decimal_places=3,
        label="Amount",
        help_text="Transaction amount",
    )
    description = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Line item description",
            }
        ),
        label="Description",
        required=False,
    )

    def clean(self):
        """Validate that amount is positive"""
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount")

        if amount and amount.amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")

        return cleaned_data


class BulkVoucherLineItemForm(forms.Form):
    """
    Bulk upload form for adding multiple line items.
    Accepts CSV or JSON format.
    """

    CSV_FORMAT = "csv"
    JSON_FORMAT = "json"
    FORMAT_CHOICES = [
        (CSV_FORMAT, "CSV (Ledger, Account, Side, Amount, Description)"),
        (JSON_FORMAT, "JSON"),
    ]

    format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        widget=forms.RadioSelect(),
        label="File Format",
    )
    file = forms.FileField(
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": ".csv,.json",
            }
        ),
        label="Upload File",
        help_text="CSV or JSON file with line items",
    )

    def clean_file(self):
        """Validate file exists and is readable"""
        file = self.cleaned_data["file"]

        if file.size > 1024 * 1024:  # 1MB max
            raise forms.ValidationError("File size must be less than 1MB")

        return file


class PostVoucherForm(forms.Form):
    """
    Form for posting a voucher to journal.

    Includes confirmation and optional period override.
    """

    confirm = forms.BooleanField(
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
        label="I confirm this voucher is correct and balanced",
        help_text="Check this box to proceed with posting",
    )
    period = forms.ModelChoiceField(
        queryset=AccountingPeriod.objects.filter(status="OPEN"),
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        label="Accounting Period",
        required=False,
        help_text="Leave blank to auto-detect from voucher date",
    )


class ReverseVoucherForm(forms.Form):
    """
    Form for reversing a posted voucher.

    Includes confirmation, reason, and period selection.
    """

    confirm = forms.BooleanField(
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
        label="I confirm I want to reverse this voucher",
        help_text="This cannot be undone without creating a new reversal",
    )
    reason = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": 'Reason for reversal (e.g., "Duplicate entry", "Incorrect amount")...',
            }
        ),
        label="Reason for Reversal",
        required=False,
        help_text="Optional description of why this voucher is being reversed",
    )
    period = forms.ModelChoiceField(
        queryset=AccountingPeriod.objects.filter(status="OPEN"),
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        label="Period for Reversal Entry",
        required=False,
        help_text="Period for the reversal journal entry (defaults to original period)",
    )


# ============================================================================
# Payment Voucher Forms
# ============================================================================


class PaymentVoucherForm(forms.ModelForm):
    """Form for creating and editing payment vouchers."""
    from djmoney.forms import MoneyField
    total_amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR")
    principal_amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR", required=False)
    interest_amount = MoneyField(max_digits=13, decimal_places=2, default_currency="    INR", required=False)
    fee_amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR", required=False)
    class Meta:
        from .models import PaymentVoucher

        model = PaymentVoucher
        fields = [
            "payment_date",
            "total_amount",
            "principal_amount",
            "interest_amount",
            "fee_amount",
            "payment_method",
            "reference_number",
            "description",
            "is_final_payment",
            "create_release",
        ]
        widgets = {
            "payment_date": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            # "total_amount": forms.TextInput(
            #     attrs={
            #         "class": "form-control",
            #         "placeholder": "Enter amount in INR",
            #     }
            # ),
            # "principal_amount": forms.TextInput(
            #     attrs={
            #         "class": "form-control",
            #         "placeholder": "Principal portion (optional)",
            #     }
            # ),
            # "interest_amount": forms.TextInput(
            #     attrs={
            #         "class": "form-control",
            #         "placeholder": "Interest portion (optional)",
            #     }
            # ),
            # "fee_amount": forms.TextInput(
            #     attrs={
            #         "class": "form-control",
            #         "placeholder": "Fees/charges (optional)",
            #     }
            # ),
            "payment_method": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "reference_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Cheque no, transaction ID, bank ref, etc",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Additional notes about this payment",
                }
            ),
            "is_final_payment": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "create_release": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }
        help_texts = {
            "payment_date": "When the payment was actually made",
            "total_amount": "Total payment amount (required)",
            "principal_amount": "How much of this payment goes to principal",
            "interest_amount": "How much of this payment is interest",
            "fee_amount": "Any fees or charges associated with this payment",
            "payment_method": "How was the payment made",
            "reference_number": "Reference number for tracking (cheque no, transaction ID, etc)",
            "description": "Additional context or notes about this payment",
            "is_final_payment": "Check if this payment closes the loan",
            "create_release": "For GivenLoans: Create release document after posting",
        }


