"""
Contact app utilities and helpers for improved functionality.
Add this to: apps/tenant_apps/contact/utils.py
"""

from django.shortcuts import render
from django.http import HttpResponse
from django.utils.translation import gettext as _
from django.core.validators import RegexValidator
import re


class HTMXHelpers:
    """Utility functions for HTMX responses"""

    @staticmethod
    def response(status=200, trigger=None, redirect=None, swap_details=None):
        """
        Create an HTMX response with proper headers

        Usage:
            return HTMXHelpers.response(
                status=200,
                trigger="listChanged",
                redirect=reverse('customer_detail', args=[obj.id])
            )
        """
        response = HttpResponse(status=status)
        if trigger:
            response["HX-Trigger"] = trigger
        if redirect:
            response["HX-Redirect"] = redirect
        if swap_details:
            response["HX-Trigger-Details"] = swap_details
        return response

    @staticmethod
    def render_modal(request, template, context, block=""):
        """
        Render template with HTMX modal block support

        Usage:
            return HTMXHelpers.render_modal(
                request,
                'contact/customer_form.html',
                context,
                block='modal-body'
            )
        """
        if request.htmx and block:
            template = f"{template}#{block}"
        return render(request, template, context)

    @staticmethod
    def success_response(obj, redirect_url=None, trigger="itemCreated"):
        """Create successful response with redirect"""
        return HTMXHelpers.response(status=200, trigger=trigger, redirect=redirect_url)


class ValidationHelpers:
    """Validation utilities for Indian addresses and phone numbers"""

    # Indian phone number pattern (10 digits, starting with 6-9)
    PHONE_REGEX = RegexValidator(
        regex=r"^(\+91)?[-\s]?[6-9]\d{9}$",
        message=_("Enter a valid Indian phone number (10 digits starting with 6-9)"),
    )

    # Indian pincode (6 digits)
    PINCODE_REGEX = RegexValidator(
        regex=r"^\d{6}$", message=_("Pincode must be exactly 6 digits")
    )

    # Aadhar number (12 digits)
    AADHAR_REGEX = RegexValidator(
        regex=r"^\d{12}$", message=_("Aadhar number must be 12 digits")
    )

    # PAN number (10 characters: 5 letters, 4 digits, 1 letter)
    PAN_REGEX = RegexValidator(
        regex=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
        message=_("Invalid PAN format (e.g., ABCDE1234F)"),
    )

    @staticmethod
    def validate_phone(phone_str):
        """
        Validate Indian phone number

        Returns: (is_valid, formatted_number, error_message)
        """
        if not phone_str:
            return False, None, _("Phone number is required")

        # Remove common separators
        clean_phone = re.sub(r"[\s\-\(\)]", "", str(phone_str))

        # Check if starts with +91 and remove it
        if clean_phone.startswith("+91"):
            clean_phone = clean_phone[3:]
        elif clean_phone.startswith("91"):
            clean_phone = clean_phone[2:]

        # Check length
        if len(clean_phone) != 10:
            return False, None, _("Phone number must be 10 digits")

        # Check first digit (6-9 for Indian numbers)
        if clean_phone[0] not in "6789":
            return False, None, _("Indian phone numbers must start with 6-9")

        # Check all digits
        if not clean_phone.isdigit():
            return False, None, _("Phone number must contain only digits")

        return True, f"+91{clean_phone}", None

    @staticmethod
    def validate_pincode(pincode):
        """Validate Indian pincode (6 digits)"""
        if not pincode:
            return False, _("Pincode is required")

        if not isinstance(pincode, str) or len(pincode) != 6 or not pincode.isdigit():
            return False, _("Pincode must be exactly 6 digits")

        return True, None

    @staticmethod
    def validate_proof_number(proof_type, proof_no):
        """
        Validate proof number based on type

        proof_type: 'AA' (Aadhar), 'PN' (PAN), 'DL' (Driving License)
        """
        proof_no = str(proof_no).strip().upper()

        if proof_type == "AA":
            if not re.match(r"^\d{12}$", proof_no):
                return False, _("Aadhar must be 12 digits")

        elif proof_type == "PN":
            if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", proof_no):
                return False, _("Invalid PAN format (e.g., ABCDE1234F)")

        elif proof_type == "DL":
            if len(proof_no) < 8:
                return False, _("Driving License number seems invalid")

        return True, None


class QueryHelpers:
    """Database query optimization helpers"""

    @staticmethod
    def get_customer_with_relations(customer_id):
        """
        Get customer with all related objects pre-fetched
        Avoids N+1 query problem
        """
        from .models import Customer

        return Customer.objects.prefetch_related(
            "address",
            "contactno",
            "pics",
            "relationships_created",
            "relationships_received",
            "proofs",
            "loans_received",
        ).get(id=customer_id)

    @staticmethod
    def get_customers_with_relations():
        """
        Get all customers with relations pre-fetched
        """
        from .models import Customer

        return Customer.objects.prefetch_related("address", "contactno", "pics").filter(
            active=True
        )


class ExportHelpers:
    """Export utilities"""

    EXPORT_FORMATS = {
        "csv": _("CSV"),
        "xlsx": _("Excel"),
        "json": _("JSON"),
        "pdf": _("PDF"),
    }

    @staticmethod
    def get_export_formats():
        """Get available export formats"""
        return ExportHelpers.EXPORT_FORMATS

    @staticmethod
    def get_customer_export_data(customers):
        """
        Prepare customer data for export
        Returns list of dictionaries
        """
        data = []
        for customer in customers:
            default_address = customer.get_default_address()
            default_contact = customer.get_default_contact()

            data.append(
                {
                    "id": customer.id,
                    "name": customer.full_name,
                    "type": customer.get_customer_type_display(),
                    "phone": str(default_contact) if default_contact else "",
                    "address": str(default_address) if default_address else "",
                    "active": "Yes" if customer.active else "No",
                    "created": customer.created.date(),
                    "created_by": str(customer.created_by)
                    if customer.created_by
                    else "",
                }
            )

        return data


class FormHelpers:
    """Form helpers for consistency"""

    COMMON_WIDGETS = {
        "text": {
            "class": "form-control",
            "placeholder": _("Enter text"),
        },
        "textarea": {
            "class": "form-control",
            "rows": 3,
            "placeholder": _("Enter details"),
        },
        "select": {
            "class": "form-select",
        },
        "date": {
            "class": "form-control",
            "type": "date",
        },
    }

    @staticmethod
    def get_widget_attrs(widget_type, **extra):
        """
        Get common widget attributes

        Usage:
            phone = forms.CharField(
                widget=forms.TextInput(
                    attrs=FormHelpers.get_widget_attrs('text',
                        placeholder='+919876543210')
                )
            )
        """
        attrs = FormHelpers.COMMON_WIDGETS.get(widget_type, {}).copy()
        attrs.update(extra)
        return attrs


class CacheHelpers:
    """Cache utilities for frequently accessed data"""

    CACHE_TIMEOUT = 3600  # 1 hour

    @staticmethod
    def get_customer_addresses(customer_id):
        """Get customer addresses (cached)"""
        from django.core.cache import cache
        from .models import Customer

        cache_key = f"customer_{customer_id}_addresses"
        addresses = cache.get(cache_key)

        if addresses is None:
            customer = Customer.objects.get(id=customer_id)
            addresses = list(customer.address.all())
            cache.set(cache_key, addresses, CacheHelpers.CACHE_TIMEOUT)

        return addresses

    @staticmethod
    def clear_customer_cache(customer_id):
        """Clear customer cache"""
        from django.core.cache import cache

        cache_patterns = [
            f"customer_{customer_id}_*",
        ]

        for pattern in cache_patterns:
            cache.delete(pattern)


class MessageHelpers:
    """Messages for user feedback"""

    SUCCESS_MESSAGES = {
        "created": _("%(name)s created successfully"),
        "updated": _("%(name)s updated successfully"),
        "deleted": _("%(name)s deleted successfully"),
        "merged": _("Customers merged successfully"),
    }

    ERROR_MESSAGES = {
        "duplicate": _("This record already exists"),
        "not_found": _("Record not found"),
        "permission": _("You do not have permission for this action"),
        "validation": _("Please check your input and try again"),
    }

    @staticmethod
    def get_success_message(action, name):
        """Get success message"""
        message = MessageHelpers.SUCCESS_MESSAGES.get(action)
        if message and name:
            return message % {"name": name}
        return _("Operation completed successfully")

    @staticmethod
    def get_error_message(error_type):
        """Get error message"""
        return MessageHelpers.ERROR_MESSAGES.get(error_type, _("An error occurred"))
