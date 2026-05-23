from django import forms
from django.contrib.auth.forms import UserCreationForm

from accounts.models import User


class SignUpForm(UserCreationForm):
    display_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    is_anonymous_profile = forms.BooleanField(required=False, initial=False)
    bio = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        required=False,
    )

    class Meta:
        model = User
        fields = ("username", "email", "display_name", "is_anonymous_profile", "bio")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("username", "email", "password1", "password2"):
            if name in self.fields:
                self.fields[name].widget.attrs["class"] = "form-input"


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("display_name", "is_anonymous_profile", "bio", "email")
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "form-input"}),
            "bio": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
        }
