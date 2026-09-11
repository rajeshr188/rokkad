"""
Onboarding Forms - Step-by-step user onboarding
"""

from django import forms
from django.contrib.auth import get_user_model

from apps.orgs.models import Company

User = get_user_model()


class ProfileSetupForm(forms.ModelForm):
    """
    Step 1: Complete user profile
    """

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter your first name"}
        ),
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter your last name"}
        ),
    )

    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
        help_text="Optional: Upload a profile picture",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "profile_picture"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add helpful labels
        self.fields["first_name"].label = "First Name"
        self.fields["last_name"].label = "Last Name"
        self.fields["profile_picture"].label = "Profile Picture"


class CompanySetupForm(forms.ModelForm):
    """
    Step 2: Create or configure company/workspace
    """

    INDUSTRY_CHOICES = [
        ("", "Select Industry"),
        ("finance", "Finance & Banking"),
        ("jewelry", "Jewelry & Precious Metals"),
        ("retail", "Retail"),
        ("manufacturing", "Manufacturing"),
        ("services", "Services"),
        ("technology", "Technology"),
        ("healthcare", "Healthcare"),
        ("education", "Education"),
        ("other", "Other"),
    ]

    COMPANY_SIZE_CHOICES = [
        ("", "Select Company Size"),
        ("1-10", "1-10 employees"),
        ("11-50", "11-50 employees"),
        ("51-200", "51-200 employees"),
        ("201-500", "201-500 employees"),
        ("500+", "500+ employees"),
    ]

    name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter your company name"}
        ),
        help_text="This will be used to create your workspace",
    )

    industry = forms.ChoiceField(
        choices=INDUSTRY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    company_size = forms.ChoiceField(
        choices=COMPANY_SIZE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    logo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
        help_text="Optional: Upload your company logo",
    )

    class Meta:
        model = Company
        fields = ["name", "logo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "Company Name"
        self.fields["logo"].label = "Company Logo"

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Company.all_objects.filter(name__iexact=name).exists():
            raise forms.ValidationError(
                "A workspace with this name already exists. Please choose a different name."
            )
        return name


class TeamInviteForm(forms.Form):
    """
    Step 3: Invite team members (optional)
    """

    email_addresses = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Enter email addresses, one per line or separated by commas\n\nExample:\njohn@example.com\njane@example.com, bob@example.com",
            }
        ),
        required=False,
        help_text="Invite team members by email. You can add more later.",
        label="Team Member Emails",
    )

    def clean_email_addresses(self):
        """Parse and validate email addresses"""
        raw_text = self.cleaned_data.get("email_addresses", "").strip()

        if not raw_text:
            return []

        # Split by newlines and commas
        emails = []
        for line in raw_text.split("\n"):
            for email in line.split(","):
                email = email.strip()
                if email:
                    emails.append(email)

        # Validate each email
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError

        validated_emails = []
        invalid_emails = []

        for email in emails:
            try:
                validate_email(email)
                validated_emails.append(email)
            except DjangoValidationError:
                invalid_emails.append(email)

        if invalid_emails:
            raise forms.ValidationError(
                f"Invalid email addresses: {', '.join(invalid_emails)}"
            )

        # Remove duplicates
        validated_emails = list(set(validated_emails))

        # Limit to 10 invites during onboarding
        if len(validated_emails) > 10:
            raise forms.ValidationError(
                "You can invite up to 10 team members during onboarding. "
                "More can be added later from team settings."
            )

        return validated_emails


class TourPreferencesForm(forms.Form):
    """
    Step 4: Feature tour preferences
    """

    ROLE_CHOICES = [
        ("owner", "Owner/Founder - I manage everything"),
        ("manager", "Manager - I oversee operations"),
        ("staff", "Staff - I help with borrowers and loans"),
        ("other", "Other"),
    ]

    primary_role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(),
        required=False,
        label="What best describes your role?",
        help_text="A preference only; this does not change your Workspace permissions.",
    )

    interested_features = forms.MultipleChoiceField(
        choices=[
            ("loans", "Loans and Collateral"),
            ("party", "Borrower Profiles"),
            ("rates", "Gold and Silver Reference Rates"),
            ("notify_v2", "Notifications and Reminders"),
            ("reports", "Reports & Analytics"),
        ],
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label="Which features are you most interested in?",
        help_text="Select all that apply",
    )

    skip_tour = forms.BooleanField(
        required=False,
        label="Skip the tour for now",
        help_text="You can access the help center anytime",
    )
