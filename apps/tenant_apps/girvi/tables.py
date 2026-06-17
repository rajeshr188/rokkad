from datetime import datetime
from decimal import Decimal, InvalidOperation

import django_tables2 as tables
import pytz
from django.urls import reverse
from django.utils.html import format_html, mark_safe
from django.utils.timesince import timesince

from .models import GivenLoan, LoanItem, Release, TakenLoan


def _format_decimal_2(value):
    if value is None:
        value = 0
    try:
        return f"{Decimal(str(value)).quantize(Decimal('0.01'))}"
    except (InvalidOperation, TypeError, ValueError):
        return value


class ImageColumn(tables.Column):
    def render(self, value):
        return format_html(
            '<img src="{}" width="50" height="50" class="img-fluid img-thumbnail" alt={}/>',
            value.url,
            value.name,
        )


class CheckBoxColumnWithName(tables.CheckBoxColumn):
    @property
    def header(self):
        return self.verbose_name


class LoanTable(tables.Table):
    loan_type = tables.Column(verbose_name="Type", empty_values=())
    loan_id = tables.Column(
        verbose_name="LoanID", attrs={"td": {"style": "width: 100px;"}}
    )
    loan_date = tables.Column(
        verbose_name="Date", localize=True, attrs={"td": {"style": "width: 120px;"}}
    )
    item_desc = tables.Column(
        verbose_name="Description", attrs={"td": {"style": "width: 20px;"}}
    )
    address = tables.Column(
        verbose_name="Address",
        visible=False,
        accessor="borrower.get_address",
        exclude_from_export=False,
    )
    lic = tables.Column(
        verbose_name="License",
        visible=False,
        accessor="series.license",
        exclude_from_export=False,
    )
    # pic = ImageColumn()
    # https://stackoverflow.com/questions/12939548/select-all-rows-in-django-tables2/12944647#12944647
    selection = tables.CheckBoxColumn(
        accessor="pk",
        attrs={"th__input": {"onclick": "toggle(this)"}},
        orderable=False,
        exclude_from_export=True,
    )
    # notified = tables.Column(accessor="last_notified", exclude_from_export=True)
    total_interest = tables.Column(verbose_name="Interest", localize=True, empty_values=())
    months_since_created = tables.Column(
        verbose_name="Months", exclude_from_export=True
    )
    total_weight = tables.Column(verbose_name="Weight", empty_values=())

    party = tables.Column(verbose_name="Party", empty_values=())

    def render_loan_type(self, record):
        return mark_safe('<span class="badge bg-primary-subtle text-primary-emphasis">Given</span>')

    def render_party(self, record):
        return self.render_borrower(record)

    def value_party(self, record):
        return self.value_borrower(record)

    def render_borrower(self, record):
        return format_html(
            """<a href="" hx-get="/contact/customer/detail/{}" hx-push-url="true"
                        hx-target="#content" hx-swap="innerHTML transition:true">
            {}</a>""",
            record.borrower.pk,
            record.borrower.name,
        )

    def value_borrower(self, record):
        return f"{record.borrower.name} {record.borrower.get_relatedas_display()} {record.borrower.relatedto}"

    def render_total_weight(self, record):
        gold_weight = f"G:{record.gold_weight} gms" if getattr(record, 'gold_weight', 0) > 0 else ""
        silver_weight = (
            f"S:{record.silver_weight} gms" if getattr(record, 'silver_weight', 0) > 0 else ""
        )
        bronze_weight = (
            f"B:{record.bronze_weight} gms" if getattr(record, 'bronze_weight', 0) > 0 else ""
        )

        # Combine the weights, ensuring there are no extra spaces
        weight = " ".join(filter(None, [gold_weight, silver_weight, bronze_weight]))
        return f"{weight}"

    def value_total_weight(self, record):
        gold_weight = f"G:{getattr(record, 'gold_weight', 0)} gms" if getattr(record, 'gold_weight', 0) > 0 else ""
        silver_weight = (
            f"S:{getattr(record, 'silver_weight', 0)} gms" if getattr(record, 'silver_weight', 0) > 0 else ""
        )
        bronze_weight = (
            f"B:{getattr(record, 'bronze_weight', 0)} gms" if getattr(record, 'bronze_weight', 0) > 0 else ""
        )

        # Combine the weights, ensuring there are no extra spaces
        weight = " ".join(filter(None, [gold_weight, silver_weight, bronze_weight]))
        return f"{weight}"

    def render_loan_id(self, record):
        return format_html(
            """
            <a href ="" hx-get="/girvi/girvi/loan/detail/{}/"
                        hx-target="#content" hx-swap="innerHTML transition:true"
                        
                        hx-push-url="true">{}</a>
            """,
            record.id,
            record.loan_id,
        )

    def value_loan_id(self, record):
        return record.loan_id

    def render_loan_date(self, value):
        return value.date

    def value_loan_date(self, record):
        return record.loan_date.date().isoformat()

    # is_overdue = tables.Column(verbose_name="Overdue?")
    total_due = tables.Column(verbose_name="Due", localize=True)

    def render_months_since_created(self, record):
        now = datetime.now()
        timezone = pytz.timezone("Asia/Kolkata")
        now = timezone.localize(now)

        months = getattr(record, "months_since_created", record.months_elapsed)
        return f"{months}/({timesince(record.loan_date, now)})"

    def render_total_interest(self, record):
        # Prefer annotated/property value when present, fallback to runtime calculation.
        total_interest = getattr(record, "total_interest", None)
        if total_interest is None:
            total_interest = record.interest_due()
        return total_interest

    # def render_total_due(self, record):
    #     return record.total_interest + record.loan_amount

    # def value_total_due(self, record):
    #     return record.total_due

    total_current_value = tables.Column(verbose_name="Value", empty_values=())

    def render_total_current_value(self, record):
        # Annotation may be missing for some queryset paths; fallback to model property.
        value = getattr(record, "total_current_value", None)
        if value is None:
            value = getattr(record, "current_value", None)
        return _format_decimal_2(value)

    def value_total_current_value(self, record):
        return record.total_current_value

    class Meta:
        model = GivenLoan
        fields = (
            "selection",
            "loan_type",
            "loan_id",
            "loan_date",
            "party",
            "item_desc",
            "total_weight",
            "loan_amount",
            "total_interest",
            "total_due",
            "total_current_value",
            "months_since_created",
            # "lic",
            # "is_overdue",
        )
        sequence = (
            "selection",
            "loan_type",
            "lic",
            "loan_id",
            "loan_date",
            "party",
            "address",
            "item_desc",
            "total_weight",
            "loan_amount",
            "total_current_value",
        )
        # https://stackoverflow.com/questions/37513463/how-to-change-color-of-django-tables-row
        row_attrs = {
            "class": lambda record: "table-success"
            if record.is_released
            else ("table-danger" if record.is_overdue else "")
        }
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no loans matching the search criteria..."
        template_name = "girvi/loan/table_htmx_loan_list.html"


class TakenLoanTable(tables.Table):
    loan_type = tables.Column(verbose_name="Type", empty_values=())
    loan_id = tables.Column(
        verbose_name="LoanID", attrs={"td": {"style": "width: 100px;"}}
    )
    loan_date = tables.Column(
        verbose_name="Date", localize=True, attrs={"td": {"style": "width: 120px;"}}
    )
    item_desc = tables.Column(
        verbose_name="Description", attrs={"td": {"style": "width: 20px;"}}
    )
    selection = tables.CheckBoxColumn(
        accessor="pk",
        attrs={"th__input": {"onclick": "toggle(this)"}},
        orderable=False,
        exclude_from_export=True,
    )
    total_interest = tables.Column(verbose_name="Interest", localize=True)
    months_since_created = tables.Column(
        verbose_name="Months", exclude_from_export=True
    )
    total_weight = tables.Column(verbose_name="Weight", empty_values=())

    party = tables.Column(verbose_name="Party", empty_values=())

    def render_loan_type(self, record):
        return mark_safe('<span class="badge bg-warning-subtle text-warning-emphasis">Taken</span>')

    def render_party(self, record):
        return self.render_lender(record)

    def value_party(self, record):
        return self.value_lender(record)

    def render_lender(self, record):
        return format_html(
            """<a href="" hx-get="/contact/customer/detail/{}" hx-push-url="true"
                        hx-target="#content" hx-swap="innerHTML transition:true">
            {}</a>""",
            record.lender.pk,
            record.lender.name,
        )

    def value_lender(self, record):
        return f"{record.lender.name} {record.lender.get_relatedas_display()} {record.lender.relatedto}"

    def render_total_weight(self, record):
        gold_weight = f"G:{record.gold_weight} gms" if getattr(record, "gold_weight", 0) > 0 else ""
        silver_weight = (
            f"S:{record.silver_weight} gms" if getattr(record, "silver_weight", 0) > 0 else ""
        )
        bronze_weight = (
            f"B:{record.bronze_weight} gms" if getattr(record, "bronze_weight", 0) > 0 else ""
        )
        return " ".join(filter(None, [gold_weight, silver_weight, bronze_weight]))

    def render_loan_id(self, record):
        detail_url = reverse("girvi:taken_loan_collateral_detail", kwargs={"loan_id": record.id})
        return format_html(
            """
            <a href ="" hx-get="{}"
                        hx-target="#content" hx-swap="innerHTML transition:true"
                        hx-push-url="true">{}</a>
            """,
            detail_url,
            record.loan_id,
        )

    def value_loan_id(self, record):
        return record.loan_id

    def render_loan_date(self, value):
        return value.date

    total_due = tables.Column(verbose_name="Due", localize=True)
    total_current_value = tables.Column(verbose_name="Value")

    def render_total_current_value(self, record):
        value = getattr(record, "total_current_value", None)
        if value is None:
            value = getattr(record, "current_value", None)
        return _format_decimal_2(value)

    def render_months_since_created(self, record):
        now = datetime.now()
        timezone = pytz.timezone("Asia/Kolkata")
        now = timezone.localize(now)
        months = getattr(record, "months_since_created", record.months_elapsed)
        return f"{months}/({timesince(record.loan_date, now)})"

    def render_total_interest(self, record):
        return record.interest_due()

    def value_total_current_value(self, record):
        return record.total_current_value

    class Meta:
        model = TakenLoan
        fields = (
            "selection",
            "loan_type",
            "loan_id",
            "loan_date",
            "party",
            "item_desc",
            "total_weight",
            "loan_amount",
            "total_interest",
            "total_due",
            "total_current_value",
            "months_since_created",
        )
        sequence = (
            "selection",
            "loan_type",
            "loan_id",
            "loan_date",
            "party",
            "item_desc",
            "total_weight",
            "loan_amount",
            "total_current_value",
        )
        row_attrs = {
            "class": lambda record: "table-success"
            if record.status == "Released"
            else ("table-danger" if record.is_overdue else "")
        }
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no taken loans matching the search criteria..."
        template_name = "girvi/loan/table_htmx_loan_list.html"


class UnifiedLoanTable(tables.Table):
    selection = tables.CheckBoxColumn(
        accessor="id",
        attrs={"th__input": {"onclick": "toggle(this)"}},
        orderable=False,
        exclude_from_export=True,
    )
    loan_type = tables.Column(verbose_name="Type")
    loan_id = tables.Column(verbose_name="LoanID")
    party = tables.Column(verbose_name="Party")
    loan_date = tables.DateTimeColumn(verbose_name="Date")
    status = tables.Column(verbose_name="Status")
    loan_amount = tables.Column(verbose_name="Amount")

    def render_loan_type(self, record):
        if record.get("loan_type") == "Taken":
            return mark_safe('<span class="badge bg-warning-subtle text-warning-emphasis">Taken</span>')
        return mark_safe('<span class="badge bg-primary-subtle text-primary-emphasis">Given</span>')

    def render_loan_id(self, record):
        if record.get("loan_type") == "Taken":
            url = reverse("girvi:taken_loan_collateral_detail", kwargs={"loan_id": record["id"]})
        else:
            url = f"/girvi/girvi/loan/detail/{record['id']}/"
        return format_html(
            '<a href="" hx-get="{}" hx-target="#content" hx-swap="innerHTML transition:true" hx-push-url="true">{}</a>',
            url,
            record.get("loan_id"),
        )

    class Meta:
        fields = (
            "selection",
            "loan_type",
            "loan_id",
            "loan_date",
            "party",
            "status",
            "loan_amount",
        )
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        template_name = "girvi/loan/table_htmx_loan_list.html"


class LoanItemTable(tables.Table):
    def render_loan(self, record):
        return format_html(
            """
            <a href ="" hx-get="/girvi/girvi/loan/detail/{}/"
                        hx-target="#content" 
                        hx-swap="innerHTML transition:true"
                        hx-push-url="true">{}</a>
            """,
            record.loan.id,
            record.loan.loan_id,
        )

    class Meta:
        model = LoanItem
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "loan",
            "item",
            "itemtype",
            "quantity",
            "weight",
            "purity",
            "loanamount",
            "interestrate",
            "interest",
            "itemdesc",
            "is_repledged",
        )
        order_by = "loan"
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }  # Add Bootstrap 5 classes


class ReleaseTable(tables.Table):
    release_id = tables.Column(linkify=True)
    loan = tables.Column(linkify=True)

    def render_loan(self, record):
        return format_html(
            """
            <a href ="" hx-get="/girvi/girvi/loan/detail/{}/"
                        hx-target="#content" 
                        hx-swap="innerHTML transition:true"
                        hx-push-url="true">{}</a>
            """,
            record.loan.id,
            record.loan.loan_id,
        )

    def render_release_id(self, record):
        return format_html(
            """
            <a href ="" hx-get="/girvi/girvi/release/detail/{}/"
                        hx-target="#content" hx-swap="innerHTML transition:true"
                        
                        hx-push-url="true">{}</a>
            """,
            record.id,
            record.release_id,
        )

    class Meta:
        model = Release
        fields = ("id", "release_id", "release_date")
        attrs = {"class": "table table-sm table-striped-columns table-hover"}
        empty_text = "There are no release matching the search criteria..."
        # template_name = "django_tables2/bootstrap5.html"
        template_name = "table_htmx.html"
