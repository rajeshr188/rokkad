from datetime import datetime

from django import forms
from django.contrib import admin
from import_export import fields, resources
from import_export.admin import ImportExportActionModelAdmin
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
        report_skipped = True
        import_id_fields = ("id",)
        use_bulk = True


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


class CustomerAdminForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"


class CustomerAdmin(ImportExportActionModelAdmin):
    # class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm
    resource_class = CustomerResource
    search_fields = ["id", "name", "relatedto", "Address"]
    list_display = [
        "name",
        "id",
        "created",
        "updated",
        "Address",
        "area",
        "customer_type",
        "relatedas",
        "relatedto",
    ]
    # readonly_fields = [
    #     "name",
    #     "id",
    #     "created",
    #     "updated",
    #     "Address",
    #     "area",
    #     "customer_type",
    #     "relatedas",
    #     "relatedto",
    # ]


class AddressAdminForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = "__all__"


class AddressAdmin(admin.ModelAdmin):
    resource_class = AddressResource
    form = AddressAdminForm
    list_display = [
        "area",
        "created",
        "doorno",
        "zipcode",
        "last_updated",
        "street",
    ]
    readonly_fields = [
        "area",
        "created",
        "doorno",
        "zipcode",
        "last_updated",
        "street",
    ]


class ContactAdminForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = "__all__"


class ContactAdmin(admin.ModelAdmin):
    resource_class = ContactResource
    form = ContactAdminForm
    list_display = [
        "created",
        "contact_type",
        "phone_number",
        "last_updated",
    ]
    readonly_fields = [
        "created",
        "contact_type",
        "phone_number",
        "last_updated",
    ]


class ProofAdminForm(forms.ModelForm):
    class Meta:
        model = Proof
        fields = "__all__"


class ProofAdmin(admin.ModelAdmin):
    resource_class = ProofResource
    form = ProofAdminForm
    list_display = [
        "proof_type",
        "created",
        "proof_no",
        "doc",
        "last_updated",
    ]
    readonly_fields = [
        "proof_type",
        "created",
        "proof_no",
        "doc",
        "last_updated",
    ]


admin.site.register(Customer, CustomerAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(Contact, ContactAdmin)
admin.site.register(Proof, ProofAdmin)
