from django import forms

from challenges.models import MAX_CHALLENGE_MARKETS
from markets.models import Market


class ChallengeCreateForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Optional challenge name",
            },
        ),
    )
    markets = forms.ModelMultipleChoiceField(
        queryset=Market.objects.filter(status=Market.Status.OPEN).order_by("title"),
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "challenge-market-checkbox"},
        ),
        error_messages={
            "required": "Select at least one event.",
        },
    )
    opponents = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "challenge-opponent-checkbox"},
        ),
        error_messages={
            "required": "Select at least one user to challenge.",
        },
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        from accounts.follow_selectors import get_mutual_followers

        mutual = get_mutual_followers(user) if user else []
        self.fields["opponents"].choices = [
            (str(u.id), u.public_name or u.username) for u in mutual
        ]

    def clean_markets(self):
        markets = self.cleaned_data.get("markets")
        if not markets:
            return markets
        if len(markets) > MAX_CHALLENGE_MARKETS:
            raise forms.ValidationError(
                f"You can select at most {MAX_CHALLENGE_MARKETS} events."
            )
        return markets

    def clean_opponents(self):
        opponents = self.cleaned_data.get("opponents")
        if not opponents:
            return opponents
        if self.user and str(self.user.id) in opponents:
            raise forms.ValidationError("You cannot challenge yourself.")
        return opponents
