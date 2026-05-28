from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from markets.models import Market
from predictions.forms import ForecastForm
from predictions.selectors import get_user_active_prediction
from predictions.services import create_prediction


@login_required
@require_http_methods(["GET", "POST"])
def create_prediction_view(request, slug):
    market = get_object_or_404(Market, slug=slug)
    existing = get_user_active_prediction(request.user, market)

    if request.method == "POST":
        if existing:
            messages.error(
                request,
                _("Your forecast cannot be changed after it is posted."),
            )
            return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}#place-forecast")

        form = ForecastForm(request.POST, market=market)
        if form.is_valid():
            create_prediction(
                user=request.user,
                market=market,
                predicted_outcome=form.cleaned_data["predicted_outcome"],
                predicted_direction=form.cleaned_data["predicted_direction"],
                reasoning=form.cleaned_data.get("reasoning", ""),
            )
            messages.success(request, _("Your forecast was posted."))
            return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}#forecasts")
    else:
        form = ForecastForm(market=market) if not existing else None

    return render(
        request,
        "predictions/prediction_form.html",
        {"form": form, "market": market, "existing": existing},
    )


@login_required
def prediction_history(request, username):
    from accounts.models import User

    user = get_object_or_404(User, username=username)
    if request.user != user and not request.user.is_staff:
        pass  # Public history is allowed per MVP
    from accounts.selectors import get_user_prediction_history

    predictions = get_user_prediction_history(user, limit=100)
    return render(
        request,
        "predictions/prediction_history.html",
        {"profile_user": user, "predictions": predictions},
    )
