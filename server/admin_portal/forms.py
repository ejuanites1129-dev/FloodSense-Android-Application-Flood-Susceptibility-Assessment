from django import forms
from django.contrib.auth.forms import AuthenticationForm


class StaffAuthenticationForm(AuthenticationForm):
    """Authenticate active staff without exposing why a login was rejected."""

    username = forms.EmailField(
        label="Work email",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "username",
                "autofocus": True,
                "placeholder": "name@example.com",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        ),
    )
    remember_device = forms.BooleanField(
        label="Remember this device",
        required=False,
        initial=False,
    )

    error_messages = {
        "invalid_login": (
            "The sign-in details are incorrect or this account is not authorized."
        ),
        "inactive": "This account is unavailable.",
        "not_staff": (
            "The sign-in details are incorrect or this account is not authorized."
        ),
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                self.error_messages["not_staff"],
                code="not_staff",
            )
