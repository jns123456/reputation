from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from markets.models import Market
from predictions.forms import ForecastForm
from predictions.models import Prediction
from predictions.selectors import get_user_active_prediction, get_user_open_predictions
from predictions.services import (
    build_duplicate_forecast_error,
    create_prediction,
    exit_prediction,
)
from reputation.services import (
    calculate_exit_reputation_delta,
    calculate_user_unrealized_reputation,
    get_predicted_outcome_probability,
)


def _build_open_position_context(prediction):
    market = prediction.market
    entry_probability = get_predicted_outcome_probability(
        prediction.predicted_outcome,
        prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )
    current_probability = get_predicted_outcome_probability(
        prediction.predicted_outcome,
        market.current_probability or {},
        predicted_direction=prediction.predicted_direction,
    )
    current_delta = calculate_exit_reputation_delta(
        predicted_outcome=prediction.predicted_outcome,
        entry_probability_snapshot=prediction.probability_at_prediction_time,
        exit_probability_snapshot=market.current_probability or {},
        predicted_direction=prediction.predicted_direction,
    )
    return {
        "prediction": prediction,
        "market": market,
        "entry_percent": int(round(entry_probability * 100)),
        "current_percent": int(round(current_probability * 100)),
        "current_delta": current_delta,
        "countdown": market.expiration_countdown,
    }


def _get_open_predictions_page_context(user):
    predictions = get_user_open_predictions(user, limit=100)
    positions = [_build_open_position_context(prediction) for prediction in predictions]
    return {
        "positions": positions,
        "total_delta": calculate_user_unrealized_reputation(user),
        "open_count": len(positions),
    }


def _exit_reputation_points(exited_prediction):
    event = exited_prediction.reputation_events.filter(
        event_type="exited_prediction"
    ).first()
    return event.points_delta if event else 0


@login_required
@require_http_methods(["GET", "POST"])
def create_prediction_view(request, slug):
    market = get_object_or_404(Market, slug=slug)
    existing = get_user_active_prediction(request.user, market)

    if request.method == "POST":
        if existing:
            messages.error(request, build_duplicate_forecast_error(user=request.user, market=market))
            anchor = (
                "#multi-outcome-forecasts"
                if len(market.outcome_labels or []) > 2
                else "#place-forecast"
            )
            return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}{anchor}")

        form = ForecastForm(request.POST, market=market)
        if form.is_valid():
            try:
                create_prediction(
                    user=request.user,
                    market=market,
                    predicted_outcome=form.cleaned_data["predicted_outcome"],
                    predicted_direction=form.cleaned_data["predicted_direction"],
                    reasoning=form.cleaned_data.get("reasoning", ""),
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                anchor = (
                    "#multi-outcome-forecasts"
                    if len(market.outcome_labels or []) > 2
                    else "#place-forecast"
                )
                return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}{anchor}")
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
@require_POST
def exit_prediction_view(request, slug, prediction_id):
    market = get_object_or_404(Market, slug=slug)
    prediction = get_object_or_404(
        Prediction,
        pk=prediction_id,
        market=market,
        user=request.user,
    )
    from_open_page = request.POST.get("source") == "open_predictions"
    is_htmx = request.headers.get("HX-Request")
    anchor = (
        "#multi-outcome-forecasts"
        if len(market.outcome_labels or []) > 2
        else "#place-forecast"
    )

    try:
        exited_prediction = exit_prediction(prediction=prediction, user=request.user)
    except ValueError as exc:
        if from_open_page and is_htmx:
            position = _build_open_position_context(prediction)
            position["exit_error"] = str(exc)
            return render(
                request,
                "predictions/partials/open_position_card.html",
                {"position": position},
                status=422,
            )
        messages.error(request, str(exc))
    except PermissionError:
        error_message = _("You cannot exit another user's forecast.")
        if from_open_page and is_htmx:
            position = _build_open_position_context(prediction)
            position["exit_error"] = str(error_message)
            return render(
                request,
                "predictions/partials/open_position_card.html",
                {"position": position},
                status=403,
            )
        messages.error(request, error_message)
    else:
        points_delta = _exit_reputation_points(exited_prediction)
        if from_open_page and is_htmx:
            page_context = _get_open_predictions_page_context(request.user)
            return render(
                request,
                "predictions/partials/exit_forecast_open_response.html",
                {
                    "prediction_id": prediction_id,
                    "points_delta": points_delta,
                    "market_title": market.display_title,
                    **page_context,
                },
            )

        event = exited_prediction.reputation_events.filter(
            event_type="exited_prediction"
        ).first()
        if event and event.points_delta >= 0:
            messages.success(
                request,
                _("Forecast exited. You earned +%(points)s reputation.")
                % {"points": event.points_delta},
            )
        elif event:
            messages.warning(
                request,
                _("Forecast exited. You realized %(points)s reputation.")
                % {"points": event.points_delta},
            )
        else:
            messages.success(request, _("Forecast exited. You can enter again."))

    if from_open_page and not is_htmx:
        return redirect(reverse("predictions:open"))

    return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}{anchor}")


@login_required
def open_predictions(request):
    return render(
        request,
        "predictions/open_predictions.html",
        _get_open_predictions_page_context(request.user),
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
