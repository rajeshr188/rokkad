from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import Company
from invitations.forms import CleanEmailMixin
from invitations.exceptions import AlreadyAccepted, AlreadyInvited, UserRegisteredEmail
from invitations.utils import get_invitation_model
from invitations.adapters import get_invitations_adapter


Invitation = get_invitation_model()

class CustomCleanEmailMixin:
    def validate_invitation(self, email):
        if Invitation.objects.all_valid().filter(email__iexact=email, accepted=False):
            raise AlreadyInvited
        elif Invitation.objects.filter(email__iexact=email, accepted=True):
            raise AlreadyAccepted
        # elif get_user_model().objects.filter(email__iexact=email):
        #     raise UserRegisteredEmail
        else:
            return True

    def clean_email(self):
        email = self.cleaned_data["email"]
        email = get_invitations_adapter().clean_email(email)

        errors = {
            "already_invited": _("This e-mail address has already been" " invited."),
            "already_accepted": _(
                "This e-mail address has already" " accepted an invite.",
            ),
            # "email_in_use": _("An active user is using this e-mail address"),
        }
        try:
            self.validate_invitation(email)
        except AlreadyInvited:
            raise forms.ValidationError(errors["already_invited"])
        except AlreadyAccepted:
            raise forms.ValidationError(errors["already_accepted"])
        # except UserRegisteredEmail:
        #     raise forms.ValidationError(errors["email_in_use"])
        return email

class CompanyInvitationForm(CustomCleanEmailMixin, forms.ModelForm):
    email = forms.EmailField(
        label=_("E-mail"),
        required=True,
        widget=forms.TextInput(attrs={"type": "email", "size": "30"}),
        initial="",
    )

    class Meta:
        model = Invitation
        fields = ('email', 'company','inviter')
    
    def __init__(self, *args, **kwargs):
        self.inviter = kwargs.pop('inviter', None)
        self.request = kwargs.pop('request', None)
        super(CompanyInvitationForm, self).__init__(*args, **kwargs)
        if self.inviter:
            self.fields['company'].queryset = Company.objects.filter(owner=self.inviter)
            self.fields['inviter'].widget = forms.HiddenInput()

    def save(self, *args, **kwargs):
        email = self.cleaned_data.get('email')
        company = self.cleaned_data.get('company')
        params = {"email": email,"company":company, "inviter": self.inviter}

        # Check if the inviter is an owner of the company
        if not company.owner == params["inviter"]:
            raise forms.ValidationError("Only company owners can send invitations.")

        instance = Invitation.create(**params)
        instance.send_invitation(self.request)
        return instance

class InvitationAdminAddForm(forms.ModelForm, CleanEmailMixin):
    email = forms.EmailField(
        label=_("E-mail"),
        required=True,
        widget=forms.TextInput(attrs={"type": "email", "size": "30"}),
    )
   
    def save(self, *args, **kwargs):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        company = cleaned_data.get("company")
        params = {"email": email,"company":company}
        if cleaned_data.get("inviter"):
            params["inviter"] = cleaned_data.get("inviter")
        instance = Invitation.create(**params)
        instance.send_invitation(self.request)
        super().save(*args, **kwargs)
        return instance

    class Meta:
        model = Invitation
        fields = ("email", "inviter","company")

class InvitationAdminChangeForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = "__all__"

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ('name',)