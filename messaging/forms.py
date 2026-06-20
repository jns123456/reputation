from django import forms
from django.utils.translation import gettext_lazy as _

from messaging.models import Message


class MessageForm(forms.Form):
    body = forms.CharField(
        max_length=Message.MAX_BODY_LENGTH,
        widget=forms.Textarea(
            attrs={
                "rows": 1,
                "class": "dm-compose-input",
                "placeholder": _("Start a new message"),
                "autocomplete": "off",
            }
        ),
    )
