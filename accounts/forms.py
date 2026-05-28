from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.avatar_services import validate_avatar_file
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
        self.fields["email"].required = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError(_("Enter a valid email address."))
        return email


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
    avatar = forms.ImageField(
        required=False,
        label=_("Profile photo"),
        help_text=_("JPEG, PNG, WebP, or GIF. Max 5 MB."),
        widget=forms.FileInput(
            attrs={
                "class": "form-input file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-brand-700",
                "accept": "image/jpeg,image/png,image/webp,image/gif",
            }
        ),
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

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        validate_avatar_file(avatar=avatar)
        return avatar

    def save(self, commit=True):
        user = super().save(commit=False)
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            from accounts.avatar_services import update_user_avatar

            if commit:
                user.save()
            update_user_avatar(user=user, avatar=avatar)
        elif commit:
            user.save()
        return user


class AvatarUploadForm(forms.Form):
    avatar = forms.ImageField(
        label=_("Profile photo"),
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp,image/gif",
                "class": "sr-only",
            }
        ),
    )

    def clean_avatar(self):
        avatar = self.cleaned_data["avatar"]
        validate_avatar_file(avatar=avatar)
        return avatar


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = (
            "notify_followed_predictions",
            "notify_new_follower",
            "notify_votes_received",
            "notify_prediction_resolved",
            "notify_challenge_updates",
            "notify_replies",
            "notify_mentions",
            "notify_market_resolving",
            "notify_in_app",
            "notify_push",
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
            "notify_replies": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_mentions": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_market_resolving": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_in_app": forms.CheckboxInput(
                attrs={"class": "rounded border-slate-300 text-brand-600 focus:ring-brand-500"}
            ),
            "notify_push": forms.CheckboxInput(
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
            "notify_replies": _("Replies to your comments"),
            "notify_mentions": _("When someone @mentions you"),
            "notify_market_resolving": _("When a market you forecast is closing soon"),
            "notify_in_app": _("In-app notifications"),
            "notify_push": _("Browser push notifications"),
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
            "notify_replies": _("Get notified when someone replies to one of your comments."),
            "notify_mentions": _("Get notified when someone mentions your @username."),
            "notify_market_resolving": _(
                "Get a reminder before a market you have an open forecast on closes."
            ),
            "notify_in_app": _("Show alerts in your notification bell."),
            "notify_push": _("Get alerts on this device even when PredictStamp isn't open (requires granting permission)."),
            "notify_email": _("Send alerts to your email address (when email is configured)."),
        }
