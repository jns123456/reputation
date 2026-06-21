from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.media_validation import clean_uploaded_image
from messaging.models import Message


class MessageForm(forms.Form):
    body = forms.CharField(
        required=False,
        max_length=Message.MAX_BODY_LENGTH,
        widget=forms.Textarea(
            attrs={
                "rows": 1,
                "class": "dm-compose-input",
                "placeholder": _("Write a message…"),
                "autocomplete": "off",
            }
        ),
    )
    image = forms.ImageField(required=False)

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()

    def clean_image(self):
        return clean_uploaded_image(self.cleaned_data.get("image"))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("body") and not cleaned.get("image"):
            raise ValidationError(_("Add a message or attach a photo."))
        return cleaned
