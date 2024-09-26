from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.fields import Field
from import_export.widgets import DateTimeWidget, ForeignKeyWidget

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import ProductVariant

from .models import License, Loan, LoanItem, LoanPayment, Release, Series


class LicenseResource(resources.ModelResource):
    class Meta:
        model = License
        import_id_fields = ("id",)
        fields = (
            "id",
            "name",
            "type",
            "shopname",
            "address",
            "phonenumber",
            "propreitor",
            "renewal_date",
        )
        created = Field(
            attribute="created",
            column_name="created",
            widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
        )
        updated = Field(
            attribute="updated",
            column_name="updated",
            widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
        )


class SeriesResource(resources.ModelResource):
    class Meta:
        model = Series
        import_id_fields = ("id",)
        fields = (
            "id",
            "name",
            "license",
            "is_active",
            # "description",
            # "prefix",
            # "start",
            # "end",
            "created",
            "last_updated",
        )
        created = Field(
            attribute="created",
            column_name="created",
            widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
        )
        last_updated = Field(
            attribute="last_updated",
            column_name="last_updated",
            widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
        )


class LoanResource(resources.ModelResource):
    created_at = Field(
        attribute="created_at",
        column_name="created_at",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    updated_at = Field(
        attribute="updated_at",
        column_name="updated_at",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    loan_date = Field(
        attribute="loan_date",
        column_name="loan_date",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    customer = fields.Field(
        column_name="customer",
        attribute="customer",
        widget=ForeignKeyWidget(Customer, "pk"),
    )
    series = fields.Field(
        column_name="series", attribute="series", widget=ForeignKeyWidget(Series, "id")
    )
    release_date = fields.Field(
        column_name="release_date",
        attribute="release__release_date",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    released_by = fields.Field(
        column_name="released_by",
        attribute="release__released_by",
        widget=ForeignKeyWidget(Customer, "pk"),
    )

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("customer", "series")
            .prefetch_related("loanitems", "loan_payments", "release")
        )
        return queryset

    class Meta:
        model = Loan
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True
        # use_bulk = True

    def before_import_row(self, row, **kwargs):
        loan_id = row.get("loan_id", "")
        if not re.match(r"^[A-Z]*\d{5}$", loan_id):
            # Modify the loan_id to match the pattern
            series_title = "".join(
                filter(str.isalpha, loan_id)
            )  # Extract letters or default to 'A'
            sequence_number = "".join(
                filter(str.isdigit, loan_id)
            )  # Extract digits or default to '00001'
            sequence_number = int(sequence_number)
            row["loan_id"] = f"{series_title}{sequence_number:05d}"


class LedgerResource(resources.ModelResource):
    customer = fields.Field(
        column_name="customer",
        attribute="customer",
        widget=ForeignKeyWidget(Customer, "id"),
    )

    def dehydrate_customer(self, loan):
        # Customize this method to include the details you want
        return f"{loan.customer.name} {loan.customer.address.first()}"

    class Meta:
        model = Loan
        fields = (
            "loan_id",
            "customer",
            "loan_date",
            "loan_amount",
            "weight",
            "value",
            "item_desc",
            "release__release_date",
            "release_released_released_by",
        )
        skip_unchanged = True
        report_skipped = True
        use_bulk = True


class LoanItemResource(resources.ModelResource):
    loan = fields.Field(
        column_name="loan", attribute="loan", widget=ForeignKeyWidget(Loan, "pk")
    )
    item = fields.Field(
        column_name="item",
        attribute="item",
        widget=ForeignKeyWidget(ProductVariant, "id"),
    )

    class Meta:
        model = LoanItem


class LoanPaymentResource(resources.ModelResource):
    created_at = Field(
        attribute="created_at",
        column_name="created_at",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    updated_at = Field(
        attribute="updated_at",
        column_name="updated_at",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    loan = fields.Field(
        column_name="loan", attribute="loan", widget=ForeignKeyWidget(Loan, "pk")
    )

    class Meta:
        model = LoanPayment


class ReleaseResource(resources.ModelResource):
    created_at = Field(
        attribute="created_at",
        column_name="created_at",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    updated_at = Field(
        attribute="updated_at",
        column_name="updated_at",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    release_date = Field(
        attribute="release_date",
        column_name="release_date",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    loan = fields.Field(
        column_name="loan", attribute="loan", widget=ForeignKeyWidget(Loan, "pk")
    )
    released_by = fields.Field(
        column_name="released_by",
        attribute="released_by",
        widget=ForeignKeyWidget(Customer, "pk"),
    )

    class Meta:
        model = Release
