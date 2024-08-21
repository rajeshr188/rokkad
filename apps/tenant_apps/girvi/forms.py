from datetime import date, datetime
from decimal import Decimal

from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row, Submit
from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy
from django.utils import timezone
from django_select2 import forms as s2forms
from django_select2.forms import (ModelSelect2Widget, Select2Mixin,
                                  Select2MultipleWidget, Select2Widget)

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import ProductVariant
from apps.tenant_apps.rates.models import Rate

from .models import (License, Loan, LoanItem, LoanPayment, Release, Series,
                     Statement, StatementItem)


class LoansWidget(s2forms.ModelSelect2Widget):
    search_fields = ["loan_id__icontains"]


class SeriesWidget(s2forms.ModelSelect2Widget):
    search_fields = ["name__icontains"]


class MultipleLoansWidget(s2forms.ModelSelect2MultipleWidget):
    search_fields = ["loan_id__icontains"]


class LicenseForm(forms.ModelForm):
    class Meta:
        model = License
        fields = [
            "name",
            "type",
            "shopname",
            "address",
            "phonenumber",
            "propreitor",
            "renewal_date",
        ]


class SeriesForm(forms.ModelForm):
    class Meta:
        model = Series
        fields = ["name", "license", "is_active"]


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
        model = Loan
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
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(
            attrs={
                "autofocus": True,
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
        queryset=Series.objects.exclude(is_active=False),
        widget=forms.Select(
            attrs={
                "hx-get": reverse_lazy("girvi:girvi_series_next_loanid"),
                "hx-target": "#div_id_lid",
                "hx-trigger": "change",
                "hx-swap": "innerHTML",
                "autofocus": True,
            }
        ),
    )

    loan_date = forms.DateTimeField(
        input_formats=["%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                # "type":"text",
                "type": "datetime-local",
                "data-date-format": "DD MMMM YYYY",
                "max": datetime.now(),
            },
            # format="%d-%m-%Y %H:%M:%S",
        ),
    )

    class Meta:
        model = Loan
        fields = [
            "loan_type",
            "series",
            "customer",
            # "pic",
            "lid",
            "loan_date",
        ]

    def clean_created(self):
        cleaned_data = super().clean()
        my_date = cleaned_data.get("loan_date")

        if my_date and my_date > timezone.now():
            raise forms.ValidationError("Date cannot be in the future.")

        return my_date

    def clean(self):
        cleaned_data = super().clean()

        if not self.cleaned_data["series"].is_active:
            self.add_error(
                "series", f"Series {self.cleaned_data['series'].name}Inactive"
            )
            # raise forms.ValidationError(
            #     f"Series {self.cleaned_data['series'].name}Inactive"
            # )

        # generate loan id when created
        loan_id = Series.objects.get(id=self.cleaned_data["series"].id).name + str(
            self.cleaned_data["lid"]
        )
        # # in update mode, check if loanid is changed
        if self.instance.loan_id and self.instance.loan_id == loan_id:
            return cleaned_data
        # when created, check if loanid already exists
        if Loan.objects.filter(loan_id=loan_id).exists():
            self.add_error("lid", "A loan with this LoanID already exists.")
            # raise forms.ValidationError("A loan with this LoanID already exists.")


class LoanRenewForm(forms.Form):
    amount = forms.IntegerField()
    interest = forms.IntegerField()


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
        widget=forms.Select(
            attrs={
                "hx-get": reverse_lazy("girvi:girvi_get_interestrate"),
                "hx-target": "#div_id_interestrate",
                "hx-trigger": "change,load",
                "hx-swap": "innerHTML",
            }
        ),
    )
    loanamount = forms.DecimalField(required=True)

    class Meta:
        model = LoanItem
        fields = [
            "pic",
            "item",
            "itemdesc",
            "itemtype",
            "quantity",
            "weight",
            "purity",
            "loanamount",
            "interestrate",
        ]

    def clean_loan(self):
        loan = self.cleaned_data["loan"]
        if loan.is_released():
            raise forms.ValidationError("Loan already has a release.")
        return loan

    def clean(self):
        cleaned_data = super().clean()

        loanamount = cleaned_data.get("loanamount")
        if loanamount is None:
            return cleaned_data
        weight = self.cleaned_data["weight"]
        purity = self.cleaned_data["purity"]
        itemtype = self.cleaned_data["itemtype"]
        rate = (
            Rate.objects.filter(metal=itemtype).latest("timestamp").buying_rate
            if Rate.objects.filter(metal=itemtype).exists()
            else 0
        )
        value = round(weight * purity * Decimal(0.01) * rate)

        if value < loanamount:
            raise forms.ValidationError(
                f"Loan amount {loanamount} cannot exceed items value {value}."
            )

        return cleaned_data


class LoanSelectionForm(forms.Form):
    loans = forms.ModelMultipleChoiceField(
        queryset=Loan.objects.all(), widget=MultipleLoansWidget
    )


class ReleaseForm(forms.ModelForm):
    release_date = forms.DateTimeField(
        input_formats=["%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime",
                "max": datetime.now(),
            },
            format="%d-%m-%Y %H:%M:%S",
        ),
    )
    loan = forms.ModelChoiceField(widget=LoansWidget, queryset=Loan.unreleased.all())
    released_by = forms.ModelChoiceField(
        required=False,
        queryset=Customer.objects.all(),
        widget=CustomerWidget(),
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

    def clean_loan(self):
        loan = self.cleaned_data["loan"]
        # if loan.due() > 0:
        #     self.add_error("loan", "Loan is not fully paid")
        # raise forms.ValidationError("Loan is not fully paid")

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

        if release_amount > loan.due():
            self.add_error(
                "release_amount",
                f"Release amount {release_amount} cannot be > due amount {loan.due()}.",
            )
            # raise ValidationError(f"Release amount {release_amount} cannot be > due amount {loan.due()}.")

        return release_amount

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Get the value of release_amount
        release_amount = self.cleaned_data.get("release_amount")

        # Create a new object in OtherModel with release_amount
        if release_amount is not None and release_amount > 0:
            payment = LoanPayment.objects.create(
                loan=instance.loan,
                payment_amount=release_amount,
                payment_date=instance.release_date,
                with_release=True,
            )

        if commit:
            instance.save()
        return instance


ReleaseFormSet = forms.modelformset_factory(Release, form=ReleaseForm, extra=1)


class BulkReleaseForm(forms.Form):
    date = forms.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "data-date-format": "DD MMMM YYYY",
                "max": datetime.now().strftime("%Y-%m-%d"),
                "autofocus": True,
            }
        ),
        initial=timezone.now(),
    )
    loans = forms.ModelMultipleChoiceField(
        widget=MultipleLoansWidget, queryset=Loan.unreleased.all()
    )


class StatementItemForm(forms.ModelForm):
    loan = forms.ModelMultipleChoiceField(
        widget=MultipleLoansWidget,
        queryset=Loan.objects.unreleased().filter(series__is_active=True),
    )

    class Meta:
        model = StatementItem
        fields = "__all__"


class LoanPaymentForm(forms.ModelForm):
    payment_date = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "data-date-format": "DD MMMM YYYY",
            }
        )
    )
    loan = forms.ModelChoiceField(
        queryset=Loan.unreleased.all(),
        widget=ModelSelect2Widget(
            model=Loan,
            queryset=Loan.unreleased.all(),
            search_fields=["loan_id__icontains"],
            # dependent_fields={'customer':'customer'}
        ),
    )
    payment_amount = forms.DecimalField()
    with_release = forms.BooleanField(
        required=False, initial=False, widget=forms.CheckboxInput()
    )

    class Meta:
        model = LoanPayment
        fields = ["payment_date", "loan", "payment_amount", "with_release"]

    def clean_loan(self):
        loan = self.cleaned_data.get("loan")
        if loan.is_released:
            raise forms.ValidationError("Loan already has a release.")
        return loan

    def clean(self):
        payment_amount = self.cleaned_data["payment_amount"]
        loan = self.cleaned_data["loan"]

        if payment_amount < 0:
            self.add_error("payment_amount", "Payment amount cannot be negative.")
            # raise forms.ValidationError("Payment amount cannot be negative.")

        if (
            payment_amount is not None
            and loan is not None
            and payment_amount > loan.due()
        ):
            self.add_error(
                "payment_amount",
                f"Payment amount {payment_amount} cannot be > due amount {loan.due()}.",
            )
            # raise ValidationError(f"Payment amount {payment_amount} cannot be > due amount {loan.due()}.")

        return self.cleaned_data
