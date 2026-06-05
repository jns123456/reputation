from django import forms
from django.utils.translation import gettext_lazy as _

from challenges.models import MAX_CHALLENGE_MARKETS, ChallengeGroup
from markets.models import Market
from markets.selectors import forecastable_market_q


class ChallengeGroupForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": _("Group name"),
            },
        ),
    )
    members = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "challenge-opponent-checkbox"},
        ),
        error_messages={
            "required": _("Select at least one member."),
        },
    )

    def __init__(self, *args, user=None, initial_members=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        from challenges.selectors import get_challengeable_users

        challengeable = get_challengeable_users(user=user) if user else []
        self.fields["members"].choices = [
            (str(u.id), u.public_name or u.username) for u in challengeable
        ]
        if initial_members is not None:
            self.fields["members"].initial = [str(uid) for uid in initial_members]


class ChallengeCreateForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": _("Optional challenge name"),
            },
        ),
    )
    markets = forms.ModelMultipleChoiceField(
        queryset=Market.objects.filter(
            forecastable_market_q(),
            source=Market.Source.POLYMARKET,
        ).order_by("title"),
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "challenge-market-checkbox"},
        ),
        error_messages={
            "required": _("Select at least one event."),
        },
    )
    opponents = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "challenge-opponent-checkbox"},
        ),
        error_messages={
            "required": _("Select at least one user to challenge."),
        },
    )
    challenge_group = forms.ModelChoiceField(
        queryset=ChallengeGroup.objects.none(),
        required=False,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        from challenges.selectors import get_challengeable_users

        challengeable = get_challengeable_users(user=user) if user else []
        self.fields["opponents"].choices = [
            (str(u.id), u.public_name or u.username) for u in challengeable
        ]
        if user:
            self.fields["challenge_group"].queryset = ChallengeGroup.objects.filter(
                owner=user,
            ).prefetch_related("members")

    def clean_markets(self):
        markets = self.cleaned_data.get("markets")
        if not markets:
            return markets
        if len(markets) > MAX_CHALLENGE_MARKETS:
            raise forms.ValidationError(
                _("You can select at most %(max)s events.") % {"max": MAX_CHALLENGE_MARKETS}
            )
        return markets

    def clean_opponents(self):
        opponents = self.cleaned_data.get("opponents") or []
        if self.user and str(self.user.id) in opponents:
            raise forms.ValidationError(_("You cannot challenge yourself."))
        return opponents

    def clean(self):
        cleaned_data = super().clean()
        opponents = cleaned_data.get("opponents") or []
        challenge_group = cleaned_data.get("challenge_group")

        if challenge_group:
            if challenge_group.owner_id != self.user.id:
                raise forms.ValidationError(_("You can only use your own saved groups."))
            from challenges.selectors import is_challengeable_user

            eligible_ids = [
                str(member.id)
                for member in challenge_group.members.all()
                if is_challengeable_user(challenger=self.user, opponent=member)
            ]
            if not eligible_ids:
                raise forms.ValidationError(
                    _("The selected group has no members you can currently challenge."),
                )
            cleaned_data["opponents"] = eligible_ids
        elif not opponents:
            self.add_error(
                "opponents",
                _("Select at least one user to challenge, or choose a saved group."),
            )

        return cleaned_data
