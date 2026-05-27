from django import forms
from django.utils.translation import gettext_lazy as _

from comments.models import Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": _("Share your thoughts…"),
                }
            ),
        }
