from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import CustomUser


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

class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = (
            "profile_picture",
        )
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
        