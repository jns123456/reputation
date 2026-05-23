from django import forms

from predictions.models import Prediction


class ForecastForm(forms.ModelForm):
    """Binary Yes/No forecast form for open markets."""

    class Meta:
        model = Prediction
        fields = ("predicted_outcome", "reasoning")
        widgets = {
            "predicted_outcome": forms.RadioSelect,
            "reasoning": forms.Textarea(
                attrs={
                    "class": "forecast-reasoning-input",
                    "rows": 5,
                    "maxlength": "2000",
                    "placeholder": "What data, news, or logic supports your pick?",
                }
            ),
        }

    def __init__(self, *args, market=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.market = market
        labels = self._binary_outcome_labels()
        self.fields["predicted_outcome"] = forms.ChoiceField(
            choices=[(label, label) for label in labels],
            widget=forms.RadioSelect,
            label="Your forecast",
        )
        self.fields["reasoning"].required = False
        self.fields["reasoning"].label = "Explain your forecast"
        self.fields["reasoning"].help_text = "Optional — shown on your public forecast. Max 2,000 characters."

    def _binary_outcome_labels(self):
        if not self.market:
            return ["Yes", "No"]
        labels = self.market.outcome_labels
        if len(labels) == 2:
            return labels
        return ["Yes", "No"]

    def clean_predicted_outcome(self):
        outcome = self.cleaned_data["predicted_outcome"]
        allowed = self._binary_outcome_labels()
        if outcome not in allowed:
            raise forms.ValidationError("Choose Yes or No for this market.")
        return outcome

    def clean(self):
        cleaned = super().clean()
        if self.market and not self.market.is_open:
            raise forms.ValidationError("This market is no longer open for forecasts.")
        return cleaned


# Backwards-compatible alias
PredictionForm = ForecastForm
