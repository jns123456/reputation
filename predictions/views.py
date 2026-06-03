from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from markets.models import Market
from predictions.forms import ForecastForm
from predictions.models import Prediction
from predictions.selectors import (
    get_user_active_prediction,
    get_user_closed_prediction_history,
    get_user_open_predictions,
    get_user_prediction_summary,
)
from predictions.services import (
    build_duplicate_forecast_error,
    create_prediction,
    exit_prediction,
)
from predictions.services import build_forecast_card_metrics
from reputation.services import calculate_user_unrealized_reputation

from markets.forecast_modes import ForecastMode, get_forecast_mode

from accounts import abuse_services
from accounts.write_guard import ContentRejected, write_guard_user_message


def _forecast_form_anchor(market) -> str:
    if get_forecast_mode(market) == ForecastMode.MULTI_BINARY:
        return "#multi-outcome-forecasts"
    return "#place-forecast"


def _build_open_position_context(prediction):
    metrics = build_forecast_card_metrics(prediction)
    return {
        "prediction": prediction,
        "market": prediction.market,
        "entry_percent": metrics["entry_percent"],
        "current_percent": metrics["now_percent"],
        "current_delta": metrics["pnl_delta"],
        "resolution_if_correct": metrics["resolution_if_correct"],
        "resolution_if_wrong": metrics["resolution_if_wrong"],
        "countdown": metrics["countdown"],
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
            anchor = _forecast_form_anchor(market)
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
            except (ValueError, ContentRejected) as exc:
                messages.error(request, write_guard_user_message(exc))
                return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}{_forecast_form_anchor(market)}")
            except abuse_services.RateLimitExceeded as exc:
                messages.error(request, write_guard_user_message(exc))
                return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}{_forecast_form_anchor(market)}")
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
    anchor = _forecast_form_anchor(market)

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


def prediction_history(request, username):
    from accounts.models import User

    user = get_object_or_404(User, username=username)
    status_filter = request.GET.get("status", "all")
    status = None
    if status_filter == Prediction.Status.RESOLVED:
        status = Prediction.Status.RESOLVED
    elif status_filter == Prediction.Status.EXITED:
        status = Prediction.Status.EXITED

    predictions = get_user_closed_prediction_history(user, limit=100, status=status)
    summary = get_user_prediction_summary(user)
    return render(
        request,
        "predictions/prediction_history.html",
        {
            "profile_user": user,
            "predictions": predictions,
            "prediction_summary": summary,
            "status_filter": status_filter,
        },
    )
