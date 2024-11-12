from datetime import datetime

from django import forms
from django.contrib import admin
from django.db import transaction
from import_export import fields, resources
from import_export.admin import ImportExportActionModelAdmin
from import_export.fields import Field
from import_export.widgets import DateTimeWidget

from .models import Address, Contact, Customer, CustomerPic, Proof
from .resources import AddressResource, ContactResource, CustomerResource, ProofResource


class AddressAdminForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = "__all__"


class AddressAdmin(admin.TabularInline):
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

    model = Address


class ContactAdminForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = "__all__"


class ContactAdmin(admin.TabularInline):
    resource_class = ContactResource
    form = ContactAdminForm
    list_display = [
        "created",
        "contact_type",
        "phone_number",
        "last_updated",
    ]
    readonly_fields = [
        "last_updated",
    ]
    model = Contact


class ProofAdminForm(forms.ModelForm):
    class Meta:
        model = Proof
        fields = "__all__"


class ProofAdmin(admin.TabularInline):
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
        "last_updated",
    ]
    model = Proof


class CustomerPicForm(forms.ModelForm):
    class Meta:
        model = CustomerPic
        fields = "__all__"


class CustomerPicAdmin(admin.TabularInline):
    form = CustomerPicForm
    search_fields = ["customer"]
    list_display = ["customer", "image", "is_default"]
    model = CustomerPic


class CustomerAdminForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"


class CustomerAdmin(ImportExportActionModelAdmin):
    # class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm
    resource_class = CustomerResource
    inlines = [AddressAdmin, ContactAdmin, ProofAdmin, CustomerPicAdmin]
    search_fields = ["id", "name", "relatedto", "Address"]
    list_display = [
        "name",
        "id",
        "created",
        "updated",
        "customer_type",
        "relatedas",
        "relatedto",
    ]
    readonly_fields = ["created", "updated"]
    list_filter = ["customer_type", "relatedas"]

    model = Customer


admin.site.register(Customer, CustomerAdmin)
