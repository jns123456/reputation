from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.media_validation import clean_uploaded_image
from accounts.models import SubscriberAudience
from pulse.models import Post
from pulse.poll_forms import PollValidationError, parse_poll_options_from_post, validate_poll_payload


class PostForm(forms.ModelForm):
    def __init__(self, *args, creator_program_enabled=False, **kwargs):
        super().__init__(*args, **kwargs)
        if creator_program_enabled:
            self.fields["audience"] = forms.ChoiceField(
                choices=SubscriberAudience.choices,
                initial=SubscriberAudience.PUBLIC,
                required=False,
                label=_("Who can see this post"),
                widget=forms.RadioSelect,
            )

    def cleaned_audience_value(self):
        if "audience" not in self.fields:
            return SubscriberAudience.PUBLIC
        return self.cleaned_data.get("audience") or SubscriberAudience.PUBLIC

    class Meta:
        model = Post
        fields = ["body", "image"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 1,
                    "maxlength": "200",
                    "placeholder": _(
                        "Share your take on markets, events, or the community…"
                    ),
                    "class": "x-compose-textarea form-textarea resize-none border-0 bg-transparent p-0 shadow-none focus:ring-0",
                    "data-mention-autocomplete": "",
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
