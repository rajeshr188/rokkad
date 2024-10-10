from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import CustomUser, UserProfile


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            "email",
            "username",
        )


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = (
            "email",
            "username",
        )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("workspace", "timezone", "profile_picture", "phone_number", "address")
        labels = {
            "workspace": "Workspace",
            "timezone": "Timezone",
            "profile_picture": "Profile Picture",
            "phone_number": "Phone Number",
            "address": "Address",
        }
        help_texts = {
            "workspace": "Select your workspace",
            "timezone": "Select your timezone",
            "profile_picture": "Upload a profile picture",
            "phone_number": "Enter your phone number",
            "address": "Enter your address",
        }
        error_messages = {
            "profile_picture": {
                "invalid": "Image files only",
            }
        }


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ("profile_picture",)
        labels = {
            "profile_picture": "Profile Picture",
        }
        help_texts = {
            "profile_picture": "Upload a profile picture",
        }
        error_messages = {
            "profile_picture": {
                "invalid": "Image files only",
            }
        }


class SwitchWorkspaceForm(forms.Form):
    workspace_id = forms.IntegerField(label="Workspace ID", required=True)
