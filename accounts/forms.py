from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from accounts.models import NotificationPreference, User


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_attrs = {
            "username": {"class": "form-input pl-10", "autocomplete": "username"},
            "email": {"class": "form-input pl-10", "autocomplete": "email"},
            "password1": {"class": "form-input pl-10", "autocomplete": "new-password"},
            "password2": {"class": "form-input pl-10", "autocomplete": "new-password"},
        }
        for name, attrs in field_attrs.items():
            if name in self.fields:
                self.fields[name].widget.attrs.update(attrs)


class ProfileSetupForm(forms.ModelForm):
    identity_mode = forms.ChoiceField(
        choices=User.IdentityMode.choices,
        initial=User.IdentityMode.PUBLIC,
        label=_("How do you want to appear?"),
        widget=forms.RadioSelect,
    )
    display_name = forms.CharField(
        max_length=150,
        required=False,
        label=_("Display name"),
        widget=forms.TextInput(
            attrs={
                "class": "form-input pl-10",
                "placeholder": _("How others will see you"),
            }
        ),
    )
    verification_requested = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Request verified identity"),
        help_text=_(
            "Verified accounts get a badge on their profile and posts. "
            "Our team reviews requests — no payment required."
        ),
        widget=forms.CheckboxInput(
            attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
        ),
    )
    bio = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea",
                "placeholder": _("Short bio (optional)"),
            }
        ),
        required=False,
        label=_("Bio"),
    )

    class Meta:
        model = User
        fields = ("identity_mode", "display_name", "verification_requested", "bio")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identity_mode"].widget.attrs.update(
            {"class": "sr-only peer", "x-model": "mode"}
        )

    def clean(self):
        cleaned_data = super().clean()
        identity_mode = cleaned_data.get("identity_mode")
        display_name = (cleaned_data.get("display_name") or "").strip()
        if identity_mode == User.IdentityMode.PSEUDONYM and not display_name:
            self.add_error(
                "display_name",
                _("Choose a pseudonym — it becomes your public name."),
            )
        if identity_mode == User.IdentityMode.ANONYMOUS and not display_name:
            self.add_error(
                "display_name",
                _("Pick an alias so others can recognize you without seeing your username."),
            )
        cleaned_data["display_name"] = display_name
        return cleaned_data


class ProfileEditForm(forms.ModelForm):
    identity_mode = forms.ChoiceField(
        choices=User.IdentityMode.choices,
        label=_("How do you want to appear?"),
        widget=forms.RadioSelect,
    )
    verification_requested = forms.BooleanField(
        required=False,
        label=_("Request verified identity"),
        help_text=_(
            "Verified accounts get a badge on their profile and posts. "
            "Our team reviews requests — no payment required."
        ),
        widget=forms.CheckboxInput(
            attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
        ),
    )

    class Meta:
        model = User
        fields = (
            "display_name",
            "identity_mode",
            "verification_requested",
            "bio",
            "email",
        )
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "form-input"}),
            "bio": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identity_mode"].widget.attrs.update(
            {"class": "sr-only peer", "x-model": "mode"}
        )
        if self.instance.is_verified:
            self.fields["verification_requested"].disabled = True
            self.fields["verification_requested"].help_text = _(
                "Your account is already verified."
            )

    def clean(self):
        cleaned_data = super().clean()
        identity_mode = cleaned_data.get("identity_mode")
        display_name = (cleaned_data.get("display_name") or "").strip()
        if identity_mode == User.IdentityMode.PSEUDONYM and not display_name:
            self.add_error(
                "display_name",
                _("Choose a pseudonym — it becomes your public name."),
            )
        if identity_mode == User.IdentityMode.ANONYMOUS and not display_name:
            self.add_error(
                "display_name",
                _("Pick an alias so others can recognize you without seeing your username."),
            )
        cleaned_data["display_name"] = display_name
        return cleaned_data


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
            "notify_followed_predictions": _("Forecasts from users you follow"),
            "notify_new_follower": _("When someone follows you"),
            "notify_votes_received": _("Upvotes and downvotes on your content"),
            "notify_prediction_resolved": _("When your forecasts are resolved"),
            "notify_challenge_updates": _("Challenge invitations and updates"),
            "notify_in_app": _("In-app notifications"),
            "notify_email": _("Email notifications"),
        }
        help_texts = {
            "notify_followed_predictions": _(
                "Get notified when someone you follow makes a new prediction."
            ),
            "notify_new_follower": _("Get notified when a user starts following you."),
            "notify_votes_received": _(
                "Get notified when someone likes or dislikes your comments or forecasts."
            ),
            "notify_prediction_resolved": _(
                "Get notified when a market closes and see the reputation points you gained or lost."
            ),
            "notify_challenge_updates": _(
                "Get notified about challenge invites, resolved events, and final results."
            ),
            "notify_in_app": _("Show alerts in your notification bell."),
            "notify_email": _("Send alerts to your email address (when email is configured)."),
        }
