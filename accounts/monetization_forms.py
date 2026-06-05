from decimal import Decimal, InvalidOperation

from django import forms
from django.utils.translation import gettext_lazy as _

from accounts.models import SubscriberAudience


class CreatorProgramForm(forms.Form):
    is_enabled = forms.BooleanField(
        required=False,
        label=_("Enable creator program"),
        help_text=_("Let others subscribe and publish subscriber-only forecasts and forum posts."),
    )
    tagline = forms.CharField(
        max_length=300,
        required=False,
        label=_("Public tagline"),
        widget=forms.TextInput(
            attrs={
                "class": "form-input w-full",
                "placeholder": _("What subscribers get from you"),
            }
        ),
    )
    welcome_message = forms.CharField(
        required=False,
        label=_("Welcome message"),
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea w-full",
                "rows": 4,
                "placeholder": _("Shown to new subscribers on your monetization page"),
            }
        ),
    )
    monthly_price = forms.CharField(
        required=True,
        label=_("Monthly price (USD)"),
        help_text=_("Displayed price only — no payment processing on PredictStamp yet."),
        widget=forms.TextInput(
            attrs={
                "class": "form-input w-full",
                "inputmode": "decimal",
                "placeholder": "5.00",
            }
        ),
    )

    def __init__(self, *args, program=None, **kwargs):
        super().__init__(*args, **kwargs)
        if program is not None:
            self.fields["is_enabled"].initial = program.is_enabled
            self.fields["tagline"].initial = program.tagline
            self.fields["welcome_message"].initial = program.welcome_message
            self.fields["monthly_price"].initial = program.monthly_price_display

    def clean_monthly_price(self):
        value = (self.cleaned_data.get("monthly_price") or "").strip().replace(",", ".")
        if not value:
            raise forms.ValidationError(_("Enter a monthly price."))
        try:
            price = Decimal(value)
        except InvalidOperation as exc:
            raise forms.ValidationError(_("Enter a valid price (e.g. 5 or 5.00).")) from exc
        if price < 0 or price > 999:
            raise forms.ValidationError(_("Monthly price must be between $0 and $999."))
        return price


class SubscriberAudienceMixin:
    """Optional audience field when the author has an enabled creator program."""

    audience = forms.ChoiceField(
        choices=SubscriberAudience.choices,
        required=False,
        initial=SubscriberAudience.PUBLIC,
        label=_("Who can see this"),
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, creator_program_enabled=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not creator_program_enabled:
            self.fields.pop("audience", None)

    def cleaned_audience_value(self):
        if "audience" not in self.fields:
            return SubscriberAudience.PUBLIC
        return self.cleaned_data.get("audience") or SubscriberAudience.PUBLIC
