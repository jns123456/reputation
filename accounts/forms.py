from django import forms
from django.contrib.auth.forms import UserCreationForm

from accounts.models import NotificationPreference, User


class SignUpForm(UserCreationForm):
    display_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    is_anonymous_profile = forms.BooleanField(
        required=False,
        initial=False,
        label="Use anonymous profile",
        widget=forms.CheckboxInput(
            attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
        ),
    )
    bio = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        required=False,
    )

    class Meta:
        model = User
        fields = ("username", "email", "display_name", "is_anonymous_profile", "bio")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_attrs = {
            "username": {"class": "form-input", "autocomplete": "username"},
            "email": {"class": "form-input", "autocomplete": "email"},
            "password1": {"class": "form-input", "autocomplete": "new-password"},
            "password2": {"class": "form-input", "autocomplete": "new-password"},
        }
        for name, attrs in field_attrs.items():
            if name in self.fields:
                self.fields[name].widget.attrs.update(attrs)


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("display_name", "is_anonymous_profile", "bio", "email")
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "form-input"}),
            "bio": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
        }


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = (
            "notify_followed_predictions",
            "notify_new_follower",
            "notify_votes_received",
            "notify_prediction_resolved",
            "notify_challenge_updates",
            "notify_in_app",
            "notify_email",
        )
        widgets = {
            "notify_followed_predictions": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_new_follower": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_votes_received": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_prediction_resolved": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_challenge_updates": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_in_app": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_email": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
        }
        labels = {
            "notify_followed_predictions": "Forecasts from users you follow",
            "notify_new_follower": "When someone follows you",
            "notify_votes_received": "Upvotes and downvotes on your content",
            "notify_prediction_resolved": "When your forecasts are resolved",
            "notify_challenge_updates": "Challenge invitations and updates",
            "notify_in_app": "In-app notifications",
            "notify_email": "Email notifications",
        }
        help_texts = {
            "notify_followed_predictions": (
                "Get notified when someone you follow makes a new prediction."
            ),
            "notify_new_follower": "Get notified when a user starts following you.",
            "notify_votes_received": (
                "Get notified when someone likes or dislikes your comments or forecasts."
            ),
            "notify_prediction_resolved": (
                "Get notified when a market closes and see the reputation points you gained or lost."
            ),
            "notify_challenge_updates": (
                "Get notified about challenge invites, resolved events, and final results."
            ),
            "notify_in_app": "Show alerts in your notification bell.",
            "notify_email": "Send alerts to your email address (when email is configured).",
        }
