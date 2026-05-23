from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.bookmark_selectors import is_bookmarked
from accounts.bookmark_services import toggle_bookmark
from accounts.forms import ProfileEditForm, SignUpForm
from accounts.models import Bookmark, User
from accounts.category_selectors import get_user_category_breakdown
from accounts.selectors import get_user_prediction_history


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"

    def get_success_url(self):
        return reverse("accounts:profile", kwargs={"username": self.request.user.username})


class CustomLogoutView(LogoutView):
    next_page = "dashboard:landing"


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", username=request.user.username)
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("accounts:profile", username=user.username)
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


def profile_detail(request, username):
    user = get_object_or_404(User.objects.select_related("profile"), username=username)
    predictions = get_user_prediction_history(user)
    category_breakdown = get_user_category_breakdown(user)
    return render(
        request,
        "accounts/profile_detail.html",
        {
            "profile_user": user,
            "predictions": predictions,
            "category_breakdown": category_breakdown,
        },
    )


@login_required
@require_POST
def bookmark_toggle(request):
    target_type = request.POST.get("target_type")
    target_id = request.POST.get("target_id")

    if target_type != Bookmark.TargetType.PREDICTION:
        return HttpResponseBadRequest("Invalid bookmark target")

    from predictions.models import Prediction

    prediction = get_object_or_404(Prediction, pk=int(target_id))
    toggle_bookmark(
        user=request.user,
        target_type=target_type,
        target_id=prediction.id,
    )

    if request.headers.get("HX-Request"):
        return render(
            request,
            "dashboard/partials/forum_bookmark_button.html",
            {
                "prediction": prediction,
                "is_bookmarked": is_bookmarked(
                    request.user,
                    target_type,
                    prediction.id,
                ),
            },
        )
    return redirect(request.META.get("HTTP_REFERER", "/"))
