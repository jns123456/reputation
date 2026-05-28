from django import forms
from django.utils.translation import gettext_lazy as _

from predictions.models import Prediction


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

    def __init__(self, *args, market=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.market = market
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

    def clean(self):
        cleaned = super().clean()
        if self.market and not self.market.is_open:
            raise forms.ValidationError(_("This market is no longer open for forecasts."))
        return cleaned


# Backwards-compatible alias
PredictionForm = ForecastForm
