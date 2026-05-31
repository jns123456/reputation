"""Forms for the user-facing MCP developer settings (AGENTS.md §17)."""

from django import forms
from django.utils.translation import gettext_lazy as _

from accounts.agent_services import account_allowed_scopes


class McpTokenForm(forms.Form):
    """Create an MCP token. Selectable scopes are bounded by what the account
    is allowed to use today (read-only for humans and new agents)."""

    name = forms.CharField(
        max_length=120,
        label=_("Token name"),
        help_text=_("A label to recognize this token, e.g. 'forecasting-bot'."),
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "my-agent"}),
    )
    scopes = forms.MultipleChoiceField(
        required=False,
        label=_("Scopes"),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        allowed = account_allowed_scopes(user) if user is not None else []
        self.allowed_scopes = list(allowed)
        self.fields["scopes"].choices = [(s, s) for s in allowed]
        # Default selection: all read scopes the account holds.
        self.fields["scopes"].initial = [s for s in allowed if s.endswith(":read")]

    def clean_scopes(self):
        requested = self.cleaned_data.get("scopes") or []
        invalid = [s for s in requested if s not in self.allowed_scopes]
        if invalid:
            raise forms.ValidationError(
                _("You are not allowed to grant these scopes: %(scopes)s")
                % {"scopes": ", ".join(invalid)}
            )
        return requested

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("scopes"):
            # Always grant at least read access so the token is useful.
            cleaned["scopes"] = [s for s in self.allowed_scopes if s.endswith(":read")]
        return cleaned
