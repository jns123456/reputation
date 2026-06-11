from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from accounts.account_deletion_services import can_delete_account

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
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                _("An account with this email already exists. Try signing in instead.")
            )
        return email


class StyledPasswordResetForm(PasswordResetForm):
    """Password reset request styled for the site and delivered via our email layer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": "form-input pl-10", "autocomplete": "email"}
        )

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        # Route through accounts.email_services so Resend/SMTP selection and
        # bilingual templates match every other transactional email.
        import logging

        from accounts.email_services import EmailDeliveryError, _send, absolute_url

        reset_path = reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": context["uid"], "token": context["token"]},
        )
        try:
            _send(
                subject=lambda: _("Reset your PredictStamp password"),
                recipient_email=to_email,
                template_base="password_reset",
                context={
                    "recipient": context.get("user"),
                    "reset_url": absolute_url(reset_path),
                },
            )
        except EmailDeliveryError as exc:
            # Fail silently to the visitor (anti-enumeration); log for ops.
            logging.getLogger(__name__).warning(
                "Password reset email failed for %s: %s", to_email, exc
            )


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs.update(
                {"class": "form-input pl-10", "autocomplete": "new-password"}
            )


class ProfileSetupForm(forms.ModelForm):
    OPERATION_MODE_CHOICES = (
        ("human", _("A person (no automation)")),
        ("ai_assisted", _("A person using AI assistance")),
        ("autonomous_agent", _("An autonomous AI agent")),
        ("organization_agent", _("An AI agent run by an organization")),
    )

    account_operation = forms.ChoiceField(
        choices=OPERATION_MODE_CHOICES,
        initial="human",
        label=_("Who operates this account?"),
        help_text=_(
            "Be honest — AI agents are welcome, but operating an undisclosed "
            "automated account is against the rules."
        ),
        widget=forms.RadioSelect,
    )
    agent_operator = forms.CharField(
        max_length=200,
        required=False,
        label=_("Agent operator"),
        help_text=_("The person or organization accountable for this agent."),
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    agent_public_description = forms.CharField(
        required=False,
        label=_("What does this agent do?"),
        help_text=_("Shown publicly on the agent's profile."),
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
    )
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
    hide_from_user_directory = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Hide from user directory"),
        help_text=_(
            "When enabled, you won't appear in the public user list or search. "
            "Direct profile links and your forecasts and comments still work."
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
        fields = (
            "identity_mode",
            "display_name",
            "verification_requested",
            "hide_from_user_directory",
            "bio",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["identity_mode"].widget.attrs.update(
            {"class": "sr-only peer", "x-model": "mode"}
        )
        self.fields["account_operation"].widget.attrs.update({"x-model": "operation"})

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

        # Primarily AI-controlled accounts must disclose an operator (§15/§16).
        operation = cleaned_data.get("account_operation")
        if operation in ("autonomous_agent", "organization_agent"):
            if not (cleaned_data.get("agent_operator") or "").strip():
                self.add_error(
                    "agent_operator",
                    _("Declared agents must name an accountable operator."),
                )
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
    hide_from_user_directory = forms.BooleanField(
        required=False,
        label=_("Hide from user directory"),
        help_text=_(
            "When enabled, you won't appear in the public user list or search. "
            "Direct profile links and your forecasts and comments still work."
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
            "hide_from_user_directory",
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


class AccountDeletionForm(forms.Form):
    username_confirm = forms.CharField(
        label=_("Confirm your username"),
        help_text=_("Type your username exactly to confirm permanent deletion."),
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "autocomplete": "off",
                "autocorrect": "off",
                "autocapitalize": "off",
                "spellcheck": "false",
            }
        ),
    )
    password = forms.CharField(
        label=_("Password"),
        help_text=_("Enter your current password to confirm."),
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "autocomplete": "current-password",
            }
        ),
        required=False,
    )

    confirmation_code = forms.CharField(
        label=_("Email confirmation code"),
        help_text=_("Enter the 6-digit code we emailed you."),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user is None:
            raise ValueError("AccountDeletionForm requires a user.")
        if not user.has_usable_password():
            # OAuth/password-less accounts re-authenticate with an emailed code
            # instead — a stolen session alone must not be enough to delete.
            del self.fields["password"]
        else:
            del self.fields["confirmation_code"]

    def clean(self):
        cleaned_data = super().clean()
        allowed, reason = can_delete_account(self.user)
        if not allowed:
            raise ValidationError(reason)
        return cleaned_data

    def clean_username_confirm(self):
        value = (self.cleaned_data.get("username_confirm") or "").strip()
        if value != self.user.username:
            raise ValidationError(_("Type your username exactly to confirm."))
        return value

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if "password" not in self.fields:
            return password
        if not password:
            raise ValidationError(_("Enter your password to confirm account deletion."))
        if not self.user.check_password(password):
            raise ValidationError(_("Incorrect password."))
        return password

    def clean_confirmation_code(self):
        from accounts.account_deletion_services import verify_deletion_confirmation_code

        code = (self.cleaned_data.get("confirmation_code") or "").strip()
        if "confirmation_code" not in self.fields:
            return code
        if not code:
            raise ValidationError(_("Enter the 6-digit code we emailed you."))
        if not verify_deletion_confirmation_code(self.user, code):
            raise ValidationError(_("Invalid or expired confirmation code."))
        return code


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
