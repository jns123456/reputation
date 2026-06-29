from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.media_validation import clean_uploaded_image
from comments.models import Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body", "image")
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": _("Share your thoughts…"),
                }
            ),
        }

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()

    def clean_image(self):
        return clean_uploaded_image(self.cleaned_data.get("image"))

    def clean(self):
        cleaned = super().clean()
        body = cleaned.get("body", "")
        image = cleaned.get("image")
        if not body and not image:
            raise ValidationError(_("Add text or an image to your comment."))
        return cleaned
