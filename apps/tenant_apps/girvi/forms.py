from datetime import date
from decimal import Decimal
import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Button, Column, Layout, Row, Submit
from django import forms
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django_select2 import forms as s2forms
from django_select2.forms import ModelSelect2Widget

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.selectors import active_parties
from apps.tenant_apps.product.models import ProductVariant
from apps.tenant_apps.girvi.services import RateCacheService
from apps.tenant_apps.girvi.policies import assert_loan_header_editable
from apps.tenant_apps.girvi.service_modules.id_generation import (
    validate_loan_id_unique_across_loan_tables,
)
from apps.tenant_apps.girvi.service_modules.release_form_validation import (
    ReleaseFormValidationService,
)


logger = logging.getLogger(__name__)

from .models import (
    GivenLoan,
    License,
    LicenseDocument,
    LoanItem,
    LoanItemPic,
    LoanItemStorageBox,
    LoanTemplate,
    Release,
    RepledgedLoanItem,
    Series,
    TakenLoan,
    TemplateFrame,
)


class LoansWidget(s2forms.ModelSelect2Widget):
    search_fields = ["loan_id__icontains"]


class SeriesWidget(s2forms.ModelSelect2Widget):
    search_fields = ["name__icontains"]


class BorrowerPartyWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "party_code__icontains",
        "display_name__icontains",
        "relation_name__icontains",
        "primary_phone__icontains",
        "primary_email__icontains",
    ]

    def get_queryset(self):
        return active_parties().order_by("display_name", "party_code")

    def label_from_instance(self, obj):
        parts = [obj.display_name]
        if obj.relation_display:
            parts.append(obj.relation_display)
        if obj.primary_phone:
            parts.append(obj.primary_phone)
        if obj.party_code:
            parts.append(obj.party_code)
        return " | ".join(parts)


class MultipleLoansWidget(s2forms.ModelSelect2MultipleWidget):
    search_fields = ["loan_id__icontains"]


class LicenseForm(forms.ModelForm):
    class Meta:
        model = License
        fields = [
            "name",
            "license_number",
            "type",
            "status",
            "shopname",
            "business_type",
            "address",
            "city",
            "state",
            "postal_code",
            "phonenumber",
            "email",
            "propreitor",
            "issuing_authority",
            "date_issued",
            "renewal_date",
            "date_expires",
            "is_renewable",
            "notes",
            "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "date_issued": forms.DateInput(attrs={"type": "date"}),
            "renewal_date": forms.DateInput(attrs={"type": "date"}),
            "date_expires": forms.DateInput(attrs={"type": "date"}),
        }


class LicenseDocumentForm(forms.ModelForm):
    """Form for uploading and managing license documents"""

    class Meta:
        model = LicenseDocument
        fields = [
            "document_type",
            "title",
            "description",
            "document_file",
            "expiry_date",
            "is_verified",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "document_file": forms.FileInput(
                attrs={
                    "accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png,.xlsx,.xls",
                    "class": "form-control",
                }
            ),
        }


class SeriesForm(forms.ModelForm):
    class Meta:
        model = Series
        fields = [
            "name", 
            "license", 
            "prefix", 
            "is_active", 
            "loan_type",
            "loan_count_threshold",
            "loan_amount_threshold",
            "deactivation_rule",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "loan_amount_threshold": forms.NumberInput(
                attrs={"step": "0.01", "min": "0"}
            ),
            "loan_count_threshold": forms.NumberInput(
                attrs={"min": "1"}
            ),
        }


class LoanTemplateForm(forms.ModelForm):
    class Meta:
        model = LoanTemplate
        fields = [
            "name",
            "print_option",
            "base_template",
            "dup_template",
            "terms_template",
            "form_d3_template",
            "page_width",
            "page_height",
            "is_active",
            "is_default",
        ]
        widgets = {
            "page_width": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "page_height": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }


class TemplateFrameForm(forms.ModelForm):
    class Meta:
        model = TemplateFrame
        fields = [
            "frame_name",
            "template_type",
            "field_type",
            "x_pos",
            "y_pos",
            "width",
            "height",
            "font_size",
            "font_name",
            "show_boundary",
        ]
        widgets = {
            "x_pos": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "y_pos": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "width": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "height": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "font_size": forms.NumberInput(attrs={"min": "1"}),
            "show_boundary": forms.NumberInput(attrs={"min": "0", "max": "1"}),
        }

    def __init__(self, *args, template=None, **kwargs):
        self.template = template or getattr(kwargs.get("instance"), "template", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.template is not None:
            instance.template = self.template
        if commit:
            instance.save()
        return instance


class LoanReportForm(forms.Form):
    filter_choices = (
        ("all", "All"),
        ("released", "Released"),
        ("unreleased", "Unreleased"),
    )
    start_date = forms.DateField(
        required=False,
        label="Start Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        required=False, label="End Date", widget=forms.DateInput(attrs={"type": "date"})
    )
    time_series_pattern = forms.ChoiceField(
        choices=(
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semiannually", "Semiannually"),
            ("annually", "Annually"),
        ),
        initial="annually",
    )
    filter_loans = forms.ChoiceField(
        choices=filter_choices, required=False, label="Loan Filter", initial="all"
    )

    class Meta:
        model = GivenLoan
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_date"].initial = date.today()
        self.fields["end_date"].initial = date.today()

    def get_crispy_helper(self):
        helper = FormHelper()
        helper.form_method = "POST"
        # customize the form layout as needed
        return helper

    def get_crosstab_compute_remainder(self):
        # replace with your actual implementation
        return True

    def get_filters(self):
        # return the filters to be used in the report
        # Note: the use of Q filters and kwargs filters
        filters = {}
        q_filters = []
        if self.cleaned_data["filter_loans"] == "unreleased":
            filters["release__isnull"] = True
        elif self.cleaned_data["filter_loans"] == "released":
            filters["release__isnull"] = False
        # if self.cleaned_data["method"]:
        #     filters["method"] = self.cleaned_data["method"]
        # if self.cleaned_data["response"]:
        #     filters["response"] = self.cleaned_data["response"]
        # if self.cleaned_data["other_people_only"]:
        #     q_filters.append(~Q(user=self.request.user))

        return q_filters, filters

    def get_start_date(self):
        return self.cleaned_data["start_date"]

    def get_end_date(self):
        return self.cleaned_data["end_date"]

    def get_time_series_pattern(self):
        # replace with your actual implementation
        return self.cleaned_data.get("time_series_pattern", "monthly")


class LoanForm(forms.ModelForm):
    borrower = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(
            attrs={
                "autofocus": True,
                "name": "borrower",
            }
        ),
    )
    # customer = forms.ModelChoiceField(
    #     queryset=Customer.objects.all(),
    #     widget=AutocompleteSelect(Loan._meta.get_field('customer'), admin.site,
    #     attrs={'data-dropdown-auto-width': 'true'}
    #     )
    # )

    series = forms.ModelChoiceField(
        queryset=Series.objects.active_for_loans(),
        widget=forms.Select(
            attrs={
                "hx-get": reverse_lazy("girvi:girvi_series_next_loanid"),
                "hx-target": "#div_id_loan_id",
                "hx-trigger": "change",
                "hx-swap": "innerHTML",
                "autofocus": True,
            }
        ),
    )

    loan_date = forms.DateTimeField(
        input_formats=["%d-%m-%Y %H:%M", "%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                # "type":"text",
                "type": "datetime-local",
                "data-date-format": "DD MMMM YYYY",
                # "max": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            },
            # format="%d-%m-%Y %H:%M",
            format="%Y-%m-%dT%H:%M",
        ),
    )

    class Meta:
        model = GivenLoan
        fields = [
            "series",
            "loan_id",
            "borrower",
            "loan_date",
            "tenure",
            "interest_type",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("series", css_class="form-group col-md-6 mb-0"),
                Column("loan_id", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            Row(
                Column("borrower", css_class="form-group col-md-8 mb-0"),
                Column("loan_date", css_class="form-group col-md-4 mb-0"),
                css_class="form-row",
            ),
            HTML(
                '<div class="mb-2"><a class="small" hx-get="{% url \'contact_customer_create\'%}" hx-target="#modal-content">+ Add Customer</a></div>'
            ),
            Row(
                Column("tenure", css_class="form-group col-md-6 mb-0"),
                Column("interest_type", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            HTML("<br/>"),
        )
        if self.instance and self.instance.id:
            self.post_url = reverse(
                "girvi:girvi_loan_update", kwargs={"pk": self.instance.id}
            )
        else:
            self.post_url = reverse("girvi:girvi_loan_create")

        self.helper.attrs = {
            "hx-post": self.post_url,
            "hx-target": "#modal-content",
        }

    def clean_created(self):
        cleaned_data = super().clean()
        my_date = cleaned_data.get("loan_date")

        if my_date and my_date > timezone.now():
            raise forms.ValidationError("Date cannot be in the future.")

        return my_date

    def clean_loan_id(self):
        loan_id = self.cleaned_data.get("loan_id")
        if loan_id:
            validate_loan_id_unique_across_loan_tables(
                loan_id,
                exclude_given_pk=getattr(self.instance, "pk", None),
            )
        return (loan_id or "").strip()

    def clean(self):
        cleaned_data = super().clean()

        if self.instance and self.instance.pk:
            assert_loan_header_editable(self.instance)

        series = cleaned_data.get("series")
        if series and not series.is_active:
            # Using self.add_error to add an error to the 'series' field
            self.add_error(
                "series", f"Series {series} is Inactive"
            )

            # Alternatively, using raise forms.ValidationError to stop processing
            # raise forms.ValidationError(f"Series {series} is Inactive")

        # # generate loan id when created
        # loan_id = Series.objects.get(id=self.cleaned_data["series"].id).name + str(
        #     self.cleaned_data["lid"]
        # )
        # # # in update mode, check if loanid is changed
        # if self.instance.loan_id and self.instance.loan_id == loan_id:
        #     return cleaned_data
        # when created, check if loanid already exists
        # if Loan.objects.filter(loan_id=cleaned_data['loan_id']).exists():
        #     self.add_error("loan_id", "A loan with this LoanID already exists.")
        # raise forms.ValidationError("A loan with this LoanID already exists.")


class LoanCreateForm(forms.Form):
    series = forms.ModelChoiceField(
        queryset=Series.objects.active_for_loans(),
        widget=forms.Select(
            attrs={
                "hx-get": reverse_lazy("girvi:girvi_series_next_loanid"),
                "hx-target": "#div_id_loan_id",
                "hx-trigger": "change",
                "hx-swap": "innerHTML",
                "autofocus": True,
            }
        ),
    )
    loan_id = forms.CharField(required=False)
    borrower_party = forms.ModelChoiceField(
        label="Borrower",
        queryset=Party.objects.none(),
        widget=BorrowerPartyWidget(
            attrs={
                "autofocus": True,
                "name": "borrower_party",
            }
        ),
    )
    loan_date = forms.DateTimeField(
        input_formats=["%d-%m-%Y %H:%M", "%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "data-date-format": "DD MMMM YYYY",
            },
            format="%Y-%m-%dT%H:%M",
        ),
    )
    tenure = forms.IntegerField(initial=3, min_value=1)
    interest_type = forms.ChoiceField(
        choices=GivenLoan._meta.get_field("interest_type").choices,
        initial=GivenLoan._meta.get_field("interest_type").default,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["borrower_party"].queryset = active_parties().order_by(
            "display_name",
            "party_code",
        )
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("series", css_class="form-group col-md-6 mb-0"),
                Column("loan_id", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            Row(
                Column("borrower_party", css_class="form-group col-md-8 mb-0"),
                Column("loan_date", css_class="form-group col-md-4 mb-0"),
                css_class="form-row",
            ),
            HTML(
                '<div class="mb-2"><a class="small" href="{% url \'party:party_create\' %}" target="_blank" rel="noopener">+ Add Party</a></div>'
            ),
            Row(
                Column("tenure", css_class="form-group col-md-6 mb-0"),
                Column("interest_type", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            HTML("<br/>"),
        )
        self.post_url = reverse("girvi:girvi_loan_create")
        self.helper.attrs = {
            "hx-post": self.post_url,
            "hx-target": "#modal-content",
        }

    def clean_loan_id(self):
        loan_id = self.cleaned_data.get("loan_id")
        if loan_id:
            validate_loan_id_unique_across_loan_tables(loan_id)
        return (loan_id or "").strip()

    def clean_loan_date(self):
        loan_date = self.cleaned_data.get("loan_date")
        if loan_date and loan_date > timezone.now():
            raise forms.ValidationError("Date cannot be in the future.")
        return loan_date

    def clean(self):
        cleaned_data = super().clean()
        series = cleaned_data.get("series")
        if series and not series.is_active:
            self.add_error("series", f"Series {series} is Inactive")
        return cleaned_data


class LoanRenewForm(forms.Form):
    RENEWAL_MODE_CHOICES = [
        ("PAY_AND_RENEW", "Pay & Renew — reduce principal"),
        ("TOPUP_RENEW", "Top-Up Renew — borrow more"),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("BANK", "Bank Transfer"),
        ("CHEQUE", "Cheque"),
        ("UPI", "UPI"),
    ]

    mode = forms.ChoiceField(
        choices=RENEWAL_MODE_CHOICES,
        widget=forms.RadioSelect,
        initial="PAY_AND_RENEW",
    )
    renewal_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        required=True,
    )
    interest_paid = forms.DecimalField(
        min_value=0,
        required=True,
        initial=0,
        help_text="Interest amount received from borrower",
    )
    principal_paid = forms.DecimalField(
        min_value=0,
        required=True,
        initial=0,
        help_text="Principal reduction paid by borrower (0 = carry full balance forward)",
    )
    requested_extra_amount = forms.DecimalField(
        min_value=0,
        required=False,
        initial=0,
        help_text="Additional amount to lend (Top-Up mode only)",
    )
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        initial="CASH",
        required=True,
    )
    reference_number = forms.CharField(
        max_length=100,
        required=False,
        help_text="Cheque / bank reference number (optional)",
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        extra = cleaned.get("requested_extra_amount") or 0
        if mode == "TOPUP_RENEW" and extra <= 0:
            self.add_error(
                "requested_extra_amount",
                "Top-Up mode requires a positive extra amount.",
            )
        return cleaned


class LoanItemForm(forms.ModelForm):
    item = forms.ModelChoiceField(
        queryset=ProductVariant.objects.all(),
        widget=ModelSelect2Widget(
            search_fields=["name__icontains"],
            select2_options={
                "width": "100%",
            },
        ),
        required=False,
    )
    itemdesc = forms.CharField(
        widget=forms.Textarea(attrs={"autofocus": True, "rows": "3"}),
    )
    itemtype = forms.ChoiceField(
        choices=(("Gold", "Gold"), ("Silver", "Silver"), ("Bronze", "Bronze")),
        widget=forms.Select(),
    )
    loanamount = forms.DecimalField(required=True)

    class Meta:
        model = LoanItem
        fields = [
            "item",
            "itemdesc",
            "itemtype",
            "quantity",
            "weight",
            "purity",
            "loanamount",
            "interestrate",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["itemtype"].widget.attrs.update(
            {
                "hx-get": reverse_lazy("girvi:girvi_get_interestrate"),
                "hx-target": f"#div_id_{self.add_prefix('interestrate')}",
                "hx-trigger": "change,load",
                "hx-swap": "innerHTML",
            }
        )
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("item", css_class="col-md-6"),
                Column("itemtype", css_class="col-md-3"),
                Column("interestrate", css_class="col-md-3"),
            ),
            Row(
                Column("itemdesc", css_class="col-12"),
            ),
            Row(
                Column("quantity", css_class="col-md-3"),
                Column("weight", css_class="col-md-3"),
                Column("purity", css_class="col-md-3"),
                Column("loanamount", css_class="col-md-3"),
            ),
            HTML('<div class="d-flex gap-2 mt-2">'),
            Submit("save", "Save", css_class="btn btn-success"),
            HTML(
                '<button class="btn btn-outline-secondary" type="button" {% if object %}hx-get="{{ object.get_absolute_url }}" hx-target="closest li" hx-swap="outerHTML"{% else %}_="on click transition opacity to 0 then remove #item-form"{% endif %}>Cancel</button>'
            ),
            HTML("</div>"),
        )

    def clean_loan(self):
        loan = self.cleaned_data["loan"]
        if loan.is_released:
            raise forms.ValidationError("Loan already has a release.")
        return loan

    def clean(self):
        cleaned_data = super().clean()

        loanamount = cleaned_data.get("loanamount")
        itemtype = cleaned_data.get("itemtype")
        weight = cleaned_data.get("weight")
        purity = cleaned_data.get("purity")

        if None in (loanamount, itemtype, weight, purity):
            return cleaned_data

        rate = RateCacheService.get_rate_or_none(itemtype)
        if rate is None:
            raise forms.ValidationError(
                f"{itemtype} rate is not configured. Add the current metal rate "
                "from Rates before creating this loan item."
            )

        value = round(weight * purity * Decimal(0.01) * rate)

        if value < loanamount:
            raise forms.ValidationError(
                f"Loan amount {loanamount} cannot exceed items value {value}."
            )

        return cleaned_data


class InitialLoanItemForm(LoanItemForm):
    # `interestrate` is intentionally excluded here because HTMX auto-populates it
    # for every extra row on page load. A lone auto-filled interest value should
    # not make an otherwise blank row block form submission.
    OPTIONAL_ROW_INPUTS = ("item", "itemdesc", "weight", "loanamount")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_permitted = True
        self.fields["itemtype"].required = False
        self.fields["itemtype"].initial = "Gold"
        self.fields["quantity"].required = False
        self.fields["quantity"].initial = 1
        self.fields["purity"].required = False
        self.fields["purity"].initial = 75
        self.fields["itemdesc"].required = False
        self.fields["weight"].required = False
        self.fields["loanamount"].required = False
        self.fields["interestrate"].required = False

    def _row_has_user_input(self, cleaned_data):
        return any(
            cleaned_data.get(field) not in (None, "")
            for field in self.OPTIONAL_ROW_INPUTS
        )

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data

        if not self._row_has_user_input(cleaned_data):
            return cleaned_data

        required_messages = {
            "itemdesc": "Description is required when adding an item.",
            "weight": "Weight is required when adding an item.",
            "loanamount": "Loan amount is required when adding an item.",
            "interestrate": "Interest rate is required when adding an item.",
        }
        for field_name, message in required_messages.items():
            if cleaned_data.get(field_name) in (None, ""):
                self.add_error(field_name, message)

        if cleaned_data.get("quantity") in (None, ""):
            cleaned_data["quantity"] = 1
        if cleaned_data.get("purity") in (None, ""):
            cleaned_data["purity"] = 75
        if not cleaned_data.get("itemtype"):
            cleaned_data["itemtype"] = "Gold"

        return cleaned_data


def build_initial_loan_item_formset(*, extra=3):
    return forms.formset_factory(InitialLoanItemForm, extra=extra, can_delete=True)


class RepledgedLoanItemForm(forms.ModelForm):
    original_loanitem = forms.ModelChoiceField(
        queryset=LoanItem.objects.filter(
            custody_status="in_vault", loan__release__isnull=True
        ),
        widget=ModelSelect2Widget(
            search_fields=["loan__loan_id__icontains"],
            select2_options={
                "width": "100%",
            },
        ),
        required=False,
    )

    class Meta:
        model = RepledgedLoanItem
        fields = ["original_loanitem", "repledged_loanamount", "interest_rate"]

    def __init__(self, *args, **kwargs):
        # loan = kwargs.pop('loan', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["original_loanitem"].queryset = LoanItem.objects.filter(
                Q(custody_status="in_vault", loan__release__isnull=True)
                | Q(pk=self.instance.original_loanitem.pk)
            )
        else:
            self.fields["original_loanitem"].queryset = LoanItem.objects.filter(
                custody_status="in_vault", loan__release__isnull=True
            )


class LoanSelectionForm(forms.Form):
    loans = forms.ModelMultipleChoiceField(
        queryset=GivenLoan.objects.all(), widget=MultipleLoansWidget
    )


class ReleaseForm(forms.ModelForm):
    release_date = forms.DateTimeField(
        input_formats=["%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime",
                "max": timezone.now(),
            },
            format="%d-%m-%Y %H:%M:%S",
        ),
    )
    loan = forms.ModelChoiceField(
        widget=LoansWidget,
        queryset=GivenLoan.objects.filter(
            release__isnull=True,
            series__in=Series.objects.active_for_releases()
        ),
    )
    released_by = forms.ModelChoiceField(
        required=False,
        queryset=Customer.objects.all(),
        widget=CustomerWidget,
    )
    release_amount = forms.DecimalField(required=False)

    class Meta:
        model = Release
        fields = ["loan", "release_date", "released_by", "release_amount"]
        # widgets = {
        #     'release_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        # }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loan_preview = self._resolve_loan_preview()
        if self.instance and self.instance.pk:
            self.fields["loan"].queryset = (
                GivenLoan.objects.filter(
                    release__isnull=True,
                    series__in=Series.objects.active_for_releases()
                ) | GivenLoan.objects.filter(pk=self.instance.loan.pk)
            )
            self.fields["loan"].initial = self.instance.loan
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("loan", css_class="form-group col-md-3 mb-0"),
                Column("release_date", css_class="form-group col-md-3 mb-0"),
                Column("released_by", css_class="form-group col-md-3 mb-0"),
                Column("release_amount", css_class="form-group col-md-3 mb-0"),
                css_class="form-row",
            )
        )

    def _resolve_loan_preview(self):
        loan = self.initial.get("loan")
        if isinstance(loan, GivenLoan):
            return loan

        if self.instance and self.instance.pk:
            return self.instance.loan

        raw_loan_id = self.data.get(self.add_prefix("loan")) if self.is_bound else loan
        if not raw_loan_id:
            return None

        try:
            return GivenLoan.objects.select_related("borrower").get(pk=raw_loan_id)
        except (GivenLoan.DoesNotExist, TypeError, ValueError):
            return None

    def clean_loan(self):
        loan = self.cleaned_data["loan"]
        # if loan.due() > 0:
        #     self.add_error("loan", "Loan is not fully paid")
        # raise forms.ValidationError("Loan is not fully paid")
        if self.instance and self.instance.pk:
            # Skip validation if updating an existing release
            return loan
        if loan.is_released:
            self.add_error("loan", "Loan already has a release.")
            # raise forms.ValidationError("Loan already has a release."
        return loan

    def clean_created(self):
        cleaned_data = super().clean()
        my_date = cleaned_data.get("release_date")

        if my_date and my_date > timezone.now():
            self.add_error("release_date", "Date cannot be in the future.")
            # raise forms.ValidationError("Date cannot be in the future.")

        return my_date

    def clean_release_amount(self):
        release_amount = self.cleaned_data["release_amount"]
        loan = self.cleaned_data["loan"]

        if not release_amount:
            return release_amount

        due_amount = getattr(loan, "total_due", None)
        if callable(due_amount):
            due_amount = due_amount()
        if due_amount is None and hasattr(loan, "due"):
            due_amount = loan.due()

        if due_amount is None:
            return release_amount

        if release_amount > due_amount:
            self.add_error(
                "release_amount",
                f"Release amount {release_amount} cannot be > due amount {due_amount}.",
            )
            # raise ValidationError(f"Release amount {release_amount} cannot be > due amount {due_amount}.")

        return release_amount


class BaseReleaseFormSet(forms.BaseModelFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return
        ReleaseFormValidationService.validate_formset(self)


def build_release_formset(extra=0):
    return forms.modelformset_factory(
        Release,
        form=ReleaseForm,
        formset=BaseReleaseFormSet,
        extra=extra,
        can_delete=True,
    )


ReleaseFormSet = build_release_formset()


class BulkReleaseForm(forms.Form):
    date = forms.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "data-date-format": "DD MMMM YYYY",
                "default": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                # "max": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "autofocus": True,
            },
            # format="%d/%m/%Y %H:%M",
            format="%Y-%m-%dT%H:%M",
        ),
        # initial=timezone.now(),
    )
    loans = forms.ModelMultipleChoiceField(
        widget=MultipleLoansWidget,
        queryset=GivenLoan.objects.filter(release__isnull=True),
    )
    # def __init__(self,*args,**kwargs):
    #     super().__init__(*args,**kwargs)
    #     self.helper = FormHelper()
    #     self.helper.layout = Layout(
    #         Row(
    #             Column("date", css_class="form-control col-md-4 mb-0"),

    #             css_class="form-row",
    #         ),
    #         Row(
    #             Column("loans", css_class="form-control col-md-4 mb-0"),
    #             css_class="form-row",
    #         )
    #     )


from .models import StatementItem  # Import here to avoid circular imports


class StatementItemForm(forms.ModelForm):
    loan = forms.ModelChoiceField(
        widget=LoansWidget,
        queryset=GivenLoan.objects.filter(series__is_active=True),
    )

    class Meta:
        model = StatementItem
        fields = [
            "loan",
        ]

    def __init__(self, *args, **kwargs):
        statement = kwargs.pop("statement")
        super().__init__(*args, **kwargs)

        # Filter loans that are not already in the statement
        self.fields["loan"].queryset = GivenLoan.objects.filter(
            series__is_active=True
        ).exclude(id__in=statement.statementitem_set.values_list("loan_id", flat=True))
        self.fields["loan"].widget.attrs = {
            "hx-post": reverse_lazy(
                "girvi:statement_item_create", kwargs={"pk": statement.id}
            ),
            "hx-target": "#statement-items",
            "hx-swap": "afterbegin",
            "hx-trigger": "changed",
        }
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column(
                    "loan",
                    css_class="form-group col-md-12 mb-0",
                ),
                css_class="form-row",
            )
        )
        self.helper.attrs = {
            "id": "my-form",
            "hx-trigger": "submit",
            "hx-post": reverse(
                "girvi:statement_item_create", kwargs={"pk": statement.id}
            ),
            "hx-target": "#statement-items",
            "hx-swap": "afterbegin",
        }

        cancel_button = Button(
            "cancel",
            "Cancel",
            css_class="btn btn-danger",
            **{"hx-on": "click: resetForm(this)"},
        )

        self.helper.add_input(Submit("submit", "Save"))
        self.helper.add_input(cancel_button)


class LoanItemStorageBoxForm(forms.ModelForm):
    start_item_id = forms.ModelChoiceField(
        queryset=GivenLoan.objects.filter(release__isnull=True),
        to_field_name="id",
        label="Start Loan ID",
        widget=LoansWidget(),
    )
    end_item_id = forms.ModelChoiceField(
        queryset=GivenLoan.objects.filter(release__isnull=True),
        to_field_name="id",
        label="End Loan ID",
        widget=LoansWidget(),
    )

    class Meta:
        model = LoanItemStorageBox
        fields = ["name", "location", "start_item_id", "end_item_id", "item_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            logger.debug(
                "Initializing storage box loan range",
                extra={
                    "storage_box_id": self.instance.pk,
                    "start_loan_id": self.instance.start_loan_id,
                    "end_loan_id": self.instance.end_loan_id,
                },
            )
            if self.instance.start_item_id:
                self.initial["start_item_id"] = self.instance.start_item.loan_id
            if self.instance.end_item_id:
                self.initial["end_item_id"] = self.instance.end_item.loan_id

    def clean(self):
        cleaned_data = super().clean()
        # start_item_id = cleaned_data.get("start_item_id")
        # end_item_id = cleaned_data.get("end_item_id")
        # if start_item_id and end_item_id and start_item_id > end_item_id:
        #     raise forms.ValidationError("Start Loan ID must be less than End Loan ID.")

        # return cleaned_data
        start_loan = cleaned_data.get("start_item_id")
        end_loan = cleaned_data.get("end_item_id")

        if start_loan and end_loan:
            if start_loan.loan_id > end_loan.loan_id:
                raise forms.ValidationError(
                    "Start Loan ID must be less than End Loan ID."
                )

        return cleaned_data


class ApproveLoanForm(forms.Form):
    approved_by = forms.CharField(max_length=255, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["approved_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "approved_by",
            HTML(
                '<div class="alert alert-success">'
                '<strong>Approving this loan</strong> advances it to <em>Approved</em> status. '
                'No accounting entry is created at this stage — disbursement triggers that.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Approve Loan", css_class="btn btn-success"))


class SubmitForApprovalLoanForm(forms.Form):
    submitted_by = forms.CharField(
        max_length=255, widget=forms.HiddenInput(), required=False
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["submitted_by"].initial = getattr(user, "username", str(user))
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "submitted_by",
            HTML(
                '<div class="alert alert-primary">'
                '<strong>Submit for approval</strong> sends this draft loan into the checker/approval queue. '
                'Borrower, collateral, and terms must already be complete.'
                '</div>'
            ),
        )
        self.helper.add_input(
            Submit("submit", "Submit for Approval", css_class="btn btn-primary")
        )


class DisburseLoanForm(forms.Form):
    disbursed_by = forms.CharField(max_length=255, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["disbursed_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "disbursed_by",
            HTML(
                '<div class="alert alert-warning">'
                '<strong>Disbursing this loan</strong> records cash as paid out to the borrower. '
                'A <code>LOAN_DISBURSE</code> accounting entry will be created automatically.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Confirm Disbursement", css_class="btn btn-primary"))


class DeliverLoanForm(forms.Form):
    created_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    released_by = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        widget=CustomerWidget,
        label="Released To",
        required=False,
        help_text="Person receiving the collateral back (leave blank if same as borrower)",
    )
    release_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        help_text="Date/time of release (defaults to now)",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["created_by"].initial = user
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "created_by",
            Row(
                Column("released_by", css_class="col-md-6"),
                Column("release_date", css_class="col-md-6"),
            ),
            HTML(
                '<div class="alert alert-info">'
                '<strong>Releasing this loan</strong> marks the collateral as returned. '
                'Ensure all outstanding dues are settled before releasing.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Release Collateral", css_class="btn btn-info"))


class CancelLoanForm(forms.Form):
    cancelled_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "State the reason for cancellation..."}),
        label="Cancellation Reason",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["cancelled_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "cancelled_by",
            "reason",
            HTML(
                '<div class="alert alert-danger">'
                '<strong>Cancelling this loan</strong> is irreversible. '
                'The loan must be in <em>Created</em> or <em>Approved</em> status. '
                'No accounting entry is created.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Cancel Loan", css_class="btn btn-danger"))


class UndoDisburseLoanForm(forms.Form):
    undone_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "State why the disbursal is being reversed..."}),
        label="Reason for Reversal",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["undone_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "undone_by",
            "reason",
            HTML(
                '<div class="alert alert-warning">'
                '<strong>Undo Disbursal</strong> reverses the cash-out accounting entry '
                '(GIVENLOAN_DISBURSAL) and returns the loan to <em>Approved</em> status. '
                'This is only permitted if no repayment or release vouchers have been posted. '
                'Use this to correct an entry made by mistake.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Undo Disbursal", css_class="btn btn-warning"))


class UndoReleaseLoanForm(forms.Form):
    undone_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "State why the release is being reversed..."}),
        label="Reason for Reversal",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["undone_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "undone_by",
            "reason",
            HTML(
                '<div class="alert alert-warning">'
                '<strong>Undo Release</strong> reverses the cash-in accounting entry '
                '(GIVENLOAN_RELEASE), deletes the Release document, and returns the loan to '
                '<em>Disbursed</em> status. '
                'Use this to correct a release entered by mistake. '
                'The Release ID and accounting trail are preserved in the audit log.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Undo Release", css_class="btn btn-warning"))


class RepledgeLoanForm(forms.Form):
    created_by = forms.CharField(max_length=255, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["created_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "created_by",
            HTML(
                '<div class="alert alert-info">'
                '<strong>Repledge</strong> marks this loan as renewed/repledged. '
                'Collateral remains in custody and source loan moves to <em>Repledged</em>.'
                "</div>"
            ),
        )
        self.helper.add_input(
            Submit("submit", "Confirm Repledge", css_class="btn btn-info")
        )


class UndoRepledgeLoanForm(forms.Form):
    undone_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "State why repledge is being reversed..."}
        ),
        label="Reason for Reversal",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["undone_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "undone_by",
            "reason",
            HTML(
                '<div class="alert alert-warning">'
                '<strong>Undo Repledge</strong> reverses the renewal linkage and '
                'returns source loan to <em>Disbursed</em> status.'
                "</div>"
            ),
        )
        self.helper.add_input(
            Submit("submit", "Undo Repledge", css_class="btn btn-warning")
        )


class MarkDefaultedLoanForm(forms.Form):
    marked_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Describe the default circumstances..."}),
        label="Default Reason",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["marked_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "marked_by",
            "reason",
            HTML(
                '<div class="alert alert-warning">'
                '<strong>Marking as defaulted</strong> records that the borrower has not repaid. '
                'No immediate GL entry — you can proceed to auction or sell the collateral.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Mark as Defaulted", css_class="btn btn-warning"))


class RequestClosureLoanForm(forms.Form):
    requested_by = forms.CharField(
        max_length=255, widget=forms.HiddenInput(), required=False
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["requested_by"].initial = getattr(user, "username", str(user))
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "requested_by",
            HTML(
                '<div class="alert alert-info">'
                '<strong>Request Closure</strong> moves the loan into <em>Closure Pending</em>. '
                'Use this only once dues are settled and the release workflow is ready to begin.'
                '</div>'
            ),
        )
        self.helper.add_input(
            Submit("submit", "Request Closure", css_class="btn btn-info")
        )


class RequestRenewalLoanForm(forms.Form):
    requested_by = forms.CharField(
        max_length=255, widget=forms.HiddenInput(), required=False
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["requested_by"].initial = getattr(user, "username", str(user))
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "requested_by",
            HTML(
                '<div class="alert alert-info">'
                '<strong>Request Renewal</strong> moves the loan into <em>Renewal Pending</em> so the renewal '
                'terms and successor loan can be finalized safely.'
                '</div>'
            ),
        )
        self.helper.add_input(
            Submit("submit", "Request Renewal", css_class="btn btn-info")
        )


class RejectLoanForm(forms.Form):
    rejected_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "State the reason for rejection..."}),
        label="Rejection Reason",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["rejected_by"].initial = getattr(user, "username", str(user))
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "rejected_by",
            "reason",
            HTML(
                '<div class="alert alert-danger">'
                '<strong>Reject Loan</strong> ends this approval request without activating the loan. '
                'A rejection reason is required for auditability.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Reject Loan", css_class="btn btn-danger"))


class MarkNPALoanForm(forms.Form):
    marked_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Describe why this loan is now NPA..."}),
        label="NPA Reason",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["marked_by"].initial = getattr(user, "username", str(user))
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "marked_by",
            "reason",
            HTML(
                '<div class="alert alert-dark">'
                '<strong>Mark NPA</strong> escalates the loan from overdue into the non-performing asset bucket. '
                'Use this when your policy threshold has been crossed.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Mark NPA", css_class="btn btn-dark"))


class WriteOffLoanForm(forms.Form):
    written_off_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Describe the approved write-off reason..."}),
        label="Write-off Reason",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["written_off_by"].initial = getattr(user, "username", str(user))
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "written_off_by",
            "reason",
            HTML(
                '<div class="alert alert-danger">'
                '<strong>Write Off Loan</strong> recognizes an unrecoverable loss and terminates the loan. '
                'This should only be used after the authorized business decision is recorded.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Write Off Loan", css_class="btn btn-danger"))


class MarkAuctionedLoanForm(forms.Form):
    auctioned_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Auction Amount (₹)",
        help_text="Amount realised from the auction of the collateral",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["auctioned_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "auctioned_by",
            "amount",
            HTML(
                '<div class="alert alert-danger">'
                '<strong>Recording an auction</strong> will create an accounting entry for the recovered amount. '
                'This action cannot be undone.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Confirm Auction", css_class="btn btn-dark"))


class MarkSoldLoanForm(forms.Form):
    sold_by = forms.CharField(max_length=255, widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Sale Amount (₹)",
        help_text="Amount realised from the sale of the collateral",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["sold_by"].initial = user.username
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "sold_by",
            "amount",
            HTML(
                '<div class="alert alert-secondary">'
                '<strong>Recording a sale</strong> will create an accounting entry for the sale amount. '
                'This action cannot be undone.'
                '</div>'
            ),
        )
        self.helper.add_input(Submit("submit", "Confirm Sale", css_class="btn btn-secondary"))
    amount = forms.DecimalField(max_digits=10, decimal_places=2)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["sold_by"].initial = user.username


class LoanItemPicForm(forms.ModelForm):
    """Form for managing individual loan item pictures."""

    class Meta:
        model = LoanItemPic
        fields = ["pic", "description", "is_default"]
        widgets = {
            "pic": forms.FileInput(attrs={"accept": "image/*"}),
            "description": forms.Textarea(attrs={"rows": 2, "cols": 40}),
            "is_default": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("pic", css_class="col-md-6"),
                Column("is_default", css_class="col-md-3"),
                css_class="mb-3",
            ),
            Row(
                Column("description", css_class="col-12"),
            ),
        )


class GivenLoanRepaymentForm(forms.Form):
    """
    Form for recording a repayment against a GivenLoan via PaymentVoucher.
    Replaces the old LoanPaymentForm (ModelForm for LoanPayment).
    """

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("BANK", "Bank Transfer"),
        ("CHEQUE", "Cheque"),
        ("UPI", "UPI"),
        ("CARD", "Card"),
        ("OTHER", "Other"),
    ]

    total_amount = forms.DecimalField(
        label="Total Amount Received",
        min_value=Decimal("0.01"),
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
    )
    payment_date = forms.DateTimeField(
        label="Payment Date",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        ),
    )
    payment_method = forms.ChoiceField(
        label="Payment Method",
        choices=PAYMENT_METHOD_CHOICES,
        initial="CASH",
    )
    reference_number = forms.CharField(
        label="Reference / Cheque / UTR No.",
        max_length=100,
        required=False,
    )
    interest_amount = forms.DecimalField(
        label="Interest Portion",
        required=False,
        min_value=Decimal("0"),
        decimal_places=2,
        help_text="Leave blank if not splitting principal and interest.",
    )
    description = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    is_final_payment = forms.BooleanField(
        label="Final payment (closes loan)",
        required=False,
        initial=False,
    )

    def __init__(self, *args, loan=None, **kwargs):
        self.loan = loan
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get("total_amount")
        interest = cleaned_data.get("interest_amount")
        if total is not None and interest is not None and interest > total:
            self.add_error(
                "interest_amount", "Interest portion cannot exceed total amount."
            )
        if self.loan and total is not None:
            from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance

            settlement = build_loan_settlement_balance(self.loan)
            if total > settlement.total_outstanding:
                self.add_error(
                    "total_amount",
                    f"Payment amount cannot exceed outstanding amount {settlement.total_outstanding}.",
                )
            if interest is not None and interest > settlement.interest_due:
                self.add_error(
                    "interest_amount",
                    f"Interest portion cannot exceed outstanding interest {settlement.interest_due}.",
                )
        return cleaned_data


class TakenLoanRepaymentForm(forms.Form):
    """Form for recording a repayment against a TakenLoan via PaymentVoucher."""

    PAYMENT_METHOD_CHOICES = GivenLoanRepaymentForm.PAYMENT_METHOD_CHOICES

    total_amount = forms.DecimalField(
        label="Total Amount Paid",
        min_value=Decimal("0.01"),
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
    )
    payment_date = forms.DateTimeField(
        label="Payment Date",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        ),
    )
    payment_method = forms.ChoiceField(
        label="Payment Method",
        choices=PAYMENT_METHOD_CHOICES,
        initial="CASH",
    )
    reference_number = forms.CharField(
        label="Reference / Cheque / UTR No.",
        max_length=100,
        required=False,
    )
    interest_amount = forms.DecimalField(
        label="Interest Portion",
        required=False,
        min_value=Decimal("0"),
        decimal_places=2,
        help_text="Leave blank if not splitting principal and interest.",
    )
    description = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    is_final_payment = forms.BooleanField(
        label="Final payment (closes taken loan)",
        required=False,
        initial=False,
    )

    def __init__(self, *args, loan=None, **kwargs):
        self.loan = loan
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get("total_amount")
        interest = cleaned_data.get("interest_amount")
        if total is not None and interest is not None and interest > total:
            self.add_error(
                "interest_amount", "Interest portion cannot exceed total amount."
            )
        if self.loan and total is not None:
            from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance

            settlement = build_loan_settlement_balance(self.loan, loan_kind="taken")
            if total > settlement.total_outstanding:
                self.add_error(
                    "total_amount",
                    f"Payment amount cannot exceed outstanding amount {settlement.total_outstanding}.",
                )
            if interest is not None and interest > settlement.interest_due:
                self.add_error(
                    "interest_amount",
                    f"Interest portion cannot exceed outstanding interest {settlement.interest_due}.",
                )
        return cleaned_data
