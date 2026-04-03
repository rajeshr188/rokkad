from django.test import SimpleTestCase

from .forms import CustomerForm


class CustomerFormTests(SimpleTestCase):
    def test_customer_form_includes_extended_profile_fields(self):
        form = CustomerForm()

        self.assertIn("email", form.fields)
        self.assertIn("dob", form.fields)
        self.assertIn("religion", form.fields)
