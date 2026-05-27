from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from pulse.models import Post
from pulse.poll_forms import PollValidationError, parse_poll_options_from_post, validate_poll_payload

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["body", "image"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 1,
                    "maxlength": "200",
                    "placeholder": _("What's happening?"),
                    "class": "x-compose-textarea form-textarea resize-none border-0 bg-transparent p-0 shadow-none focus:ring-0",
                }
            ),
        }

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image

        max_bytes = getattr(settings, "PULSE_MAX_IMAGE_BYTES", 5 * 1024 * 1024)
        if image.size > max_bytes:
            raise ValidationError(_("Image must be 5 MB or smaller."))

        content_type = getattr(image, "content_type", "")
        if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValidationError(_("Upload a JPEG, PNG, WebP, or GIF image."))

        return image

    def clean(self):
        cleaned = super().clean()
        body = cleaned.get("body", "")
        image = cleaned.get("image")
        poll_payload = parse_poll_options_from_post(self.data)

        try:
            validate_poll_payload(
                poll_payload=poll_payload,
                body=body,
                has_image=bool(image),
            )
        except PollValidationError as exc:
            raise ValidationError(str(exc)) from exc

        if poll_payload is None and not body and not image:
            raise ValidationError(_("Add text, an image, or a poll to your post."))

        cleaned["poll_payload"] = poll_payload
        return cleaned


class CommentForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": _("Write a comment…"),
                "class": "form-textarea",
            }
        )
    )
