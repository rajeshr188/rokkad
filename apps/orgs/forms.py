from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django_select2.forms import Select2Widget
from dynamic_preferences.forms import (PreferenceForm,
                                       SinglePerInstancePreferenceForm,
                                       preference_form_builder)
from invitations.adapters import get_invitations_adapter
from invitations.exceptions import (AlreadyAccepted, AlreadyInvited,
                                    UserRegisteredEmail)
from invitations.forms import CleanEmailMixin
from invitations.utils import get_invitation_model

from .models import Company, CompanyPreferenceModel, Membership, Role
from .registries import company_preference_registry

Invitation = get_invitation_model()


class CustomCleanEmailMixin:
    def validate_invitation(self, email):
        if (
            Invitation.objects.all_valid()
            .filter(email__iexact=email, accepted=False)
            .exists()
        ):
            raise AlreadyInvited
        elif Invitation.objects.filter(email__iexact=email, accepted=True).exists():
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


class CompanyInvitationForm(forms.ModelForm):
    email = forms.EmailField(
        label=_("E-mail"),
        required=True,
        widget=forms.TextInput(attrs={"type": "email", "size": "30"}),
        initial="",
    )
    # company = forms.ModelChoiceField(
    #     label=_("Company"),
    #     required=True,
    #     queryset=Company.objects.all(),
    #     widget=Select2Widget,
    # )
    role = forms.ModelChoiceField(
        label=_("Role"),
        required=True,
        queryset=Role.objects.all(),
        widget=Select2Widget,
    )

    class Meta:
        model = Invitation
        fields = (
            "email",
            # "company",
            "role",
            "inviter",
        )

    def __init__(self, *args, **kwargs):
        self.inviter = kwargs.pop("inviter", None)
        self.request = kwargs.pop("request", None)
        self.company = kwargs.pop("company", None)
        super(CompanyInvitationForm, self).__init__(*args, **kwargs)
        if self.inviter:
            # self.fields["company"].queryset = Company.objects.filter(owner=self.inviter)
            self.fields["inviter"].widget = forms.HiddenInput()
        if self.company:
            self.fields["company"] = forms.ModelChoiceField(
                queryset=Company.objects.filter(id=self.company.id),
                initial=self.company,
                widget=forms.HiddenInput(),
            )

    def validate_invitation(self, email, company):
        if (
            Invitation.objects.all_valid()
            .filter(email__iexact=email, company=company, accepted=False)
            .exists()
        ):
            raise AlreadyInvited
        elif Invitation.objects.filter(
            email__iexact=email, company=company, accepted=True
        ).exists():
            raise AlreadyAccepted
        # elif get_user_model().objects.filter(email__iexact=email):
        #     raise UserRegisteredEmail
        else:
            return True

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        company = self.company
        errors = {
            "already_invited": _(
                f"This e-mail address has already been invited for this company."
            ),
            "already_accepted": _(
                f"This e-mail address has already accepted an invite for this company."
            ),
        }

        try:
            self.validate_invitation(email, company)
        except AlreadyInvited:
            raise forms.ValidationError(errors["already_invited"])
        except AlreadyAccepted:
            raise forms.ValidationError(errors["already_accepted"])

        return cleaned_data

    def save(self, *args, **kwargs):
        email = self.cleaned_data.get("email")
        # company = self.cleaned_data.get("company")
        role = self.cleaned_data.get("role")
        company = self.company
        params = {
            "email": email,
            "company": company,
            "role": role,
            "inviter": self.inviter,
        }

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
    role = forms.ModelChoiceField(
        label=_("Role"),
        required=True,
        queryset=Role.objects.all(),
        widget=Select2Widget,
    )

    def save(self, *args, **kwargs):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        company = cleaned_data.get("company")
        role = cleaned_data.get("role")
        params = {
            "email": email,
            "company": company,
            "role": role,
        }
        if cleaned_data.get("inviter"):
            params["inviter"] = cleaned_data.get("inviter")
        instance = Invitation.create(**params)
        instance.send_invitation(self.request)
        super().save(*args, **kwargs)
        return instance

    class Meta:
        model = Invitation
        fields = ("email", "inviter", "company", "role")


class InvitationAdminChangeForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = "__all__"


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ("name",)

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if Company.objects.filter(name=name).exists():
            raise ValidationError("Company with this name already exists.")
        return name


class CompanySinglePreferenceForm(SinglePerInstancePreferenceForm):
    class Meta:
        model = CompanyPreferenceModel
        fields = SinglePerInstancePreferenceForm.Meta.fields


class MembershipForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ("user", "company", "role")


def company_preference_form_builder(instance, Preferences=[], **kwargs):
    return preference_form_builder(
        CompanyPreferenceForm, Preferences, instance=instance, **kwargs
    )


class CompanyPreferenceForm(PreferenceForm):
    registry = company_preference_registry
