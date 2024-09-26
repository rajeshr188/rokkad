from import_export import resources
from import_export.fields import Field
from import_export.widgets import DateTimeWidget

from .models import Address, Contact, Customer, Proof


class CustomerResource(resources.ModelResource):
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

    class Meta:
        model = Customer
        skip_unchanged = True
        report_skipped = False
        import_id_fields = ("id",)
        use_bulk = True
        skip_diff = True


class AddressResource(resources.ModelResource):
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
    skip_unchanged = True
    report_skipped = True
    import_id_fields = ("id",)
    use_bulk = True

    class Meta:
        model = Address
        skip_unchanged = True
        report_skipped = True


class ContactResource(resources.ModelResource):
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
    skip_unchanged = True
    report_skipped = True
    import_id_fields = ("id",)
    use_bulk = True

    class Meta:
        model = Contact
        skip_unchanged = True


class ProofResource(resources.ModelResource):
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

    class Meta:
        model = Proof
        skip_unchanged = True
