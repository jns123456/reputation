from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from pulse.models import Post

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
                    "rows": 3,
                    "maxlength": "200",
                    "placeholder": "What's on your mind?",
                    "class": "form-textarea resize-none border-0 bg-transparent p-0 text-[15px] shadow-none focus:ring-0",
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
            raise ValidationError("Image must be 5 MB or smaller.")

        content_type = getattr(image, "content_type", "")
        if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValidationError("Upload a JPEG, PNG, WebP, or GIF image.")

        return image

    def clean(self):
        cleaned = super().clean()
        body = cleaned.get("body", "")
        image = cleaned.get("image")
        if not body and not image:
            raise ValidationError("Add text or an image to your post.")
        return cleaned


class CommentForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Write a comment…",
                "class": "form-textarea",
            }
        )
    )
