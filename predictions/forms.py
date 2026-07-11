from django import forms
from django.utils.translation import gettext_lazy as _

from accounts.models import SubscriberAudience
from predictions.debrief_services import DEBRIEF_MAX_CHARS, DEBRIEF_MIN_CHARS
from predictions.models import Prediction


class ForecastDebriefForm(forms.Form):
    """Short post-resolution reflection — distinct from pre-forecast reasoning."""

    body = forms.CharField(
        label=_("What did you learn?"),
        min_length=DEBRIEF_MIN_CHARS,
        max_length=DEBRIEF_MAX_CHARS,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "maxlength": str(DEBRIEF_MAX_CHARS),
                "placeholder": _(
                    "What went right or wrong? What would you change next time?"
                ),
                "class": "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100",
            }
        ),
        help_text=_(
            "Published once — cannot be edited. Earns popularity when others find it useful, never reputation."
        ),
    )

    def clean_body(self):
        return self.cleaned_data["body"].strip()


class ForecastForm(forms.ModelForm):
    """Forecast form for open markets (binary or multi-outcome)."""

    class Meta:
        model = Prediction
        fields = ("predicted_outcome", "predicted_direction", "reasoning")
        widgets = {
            "predicted_outcome": forms.RadioSelect,
            "predicted_direction": forms.HiddenInput,
            "reasoning": forms.Textarea(
                attrs={
                    "class": "forecast-reasoning-input",
                    "rows": 5,
                    "maxlength": "2000",
                    "placeholder": _("What data, news, or logic supports your pick?"),
                }
            ),
        }

    def __init__(self, *args, market=None, creator_program_enabled=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.market = market
        if creator_program_enabled:
            self.fields["audience"] = forms.ChoiceField(
                choices=SubscriberAudience.choices,
                initial=SubscriberAudience.PUBLIC,
                required=False,
                label=_("Who can see this forecast"),
                widget=forms.RadioSelect,
            )
        labels = self._outcome_labels()
        self.fields["predicted_outcome"] = forms.ChoiceField(
            choices=[(label, label) for label in labels],
            widget=forms.RadioSelect,
            label=_("Your forecast"),
        )
        self.fields["predicted_direction"] = forms.ChoiceField(
            choices=Prediction.Direction.choices,
            widget=forms.HiddenInput,
            initial=Prediction.Direction.YES,
            required=False,
            label=_("Forecast side"),
        )
        self.fields["reasoning"].required = False
        self.fields["reasoning"].label = _("Explain your forecast")
        self.fields["reasoning"].help_text = _(
            "Optional — shown on your public forecast. Max 2,000 characters."
        )

    def _outcome_labels(self):
        if not self.market:
            return ["Yes", "No"]
        if self.market.is_soccer_match:
            from integrations.polymarket.soccer_matches import ordered_soccer_probability_items

            items = ordered_soccer_probability_items(self.market)
            if len(items) >= 2:
                return [label for label, _prob in items]
        labels = self.market.outcome_labels
        if len(labels) >= 2:
            return labels
        return ["Yes", "No"]

    @property
    def outcome_count(self):
        return len(self._outcome_labels())

    def clean_predicted_outcome(self):
        outcome = self.cleaned_data["predicted_outcome"]
        allowed = self._outcome_labels()
        if outcome not in allowed:
            raise forms.ValidationError(_("Choose a valid outcome for this market."))
        return outcome

    def clean_predicted_direction(self):
        direction = self.cleaned_data.get("predicted_direction") or Prediction.Direction.YES
        if direction not in Prediction.Direction.values:
            raise forms.ValidationError(_("Choose Yes or No for this outcome."))
        return direction

    def cleaned_audience_value(self):
        if "audience" not in self.fields:
            return SubscriberAudience.PUBLIC
        return self.cleaned_data.get("audience") or SubscriberAudience.PUBLIC

    def clean(self):
        cleaned = super().clean()
        if self.market and not self.market.is_forecastable:
            raise forms.ValidationError(_("This market is no longer open for forecasts."))
        return cleaned


# Backwards-compatible alias
PredictionForm = ForecastForm
