from django.contrib import messages
from django.core.exceptions import ValidationError
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
from accounts.http_utils import resolve_safe_return_url
from accounts.write_guard import ContentRejected, write_guard_user_message
from markets.navigation import market_return_session_key, resolve_market_return_url


def _persist_market_return_url(request, *, slug: str) -> str:
    return_url = resolve_safe_return_url(
        request,
        exclude_paths=(
            reverse("markets:detail", kwargs={"slug": slug}),
            reverse("predictions:create", kwargs={"slug": slug}),
        ),
    )
    if return_url:
        request.session[market_return_session_key(slug)] = return_url
    return return_url or request.session.get(market_return_session_key(slug), "")


def _forecast_success_redirect(request, *, slug: str):
    _persist_market_return_url(request, slug=slug)
    detail_url = reverse("markets:detail", kwargs={"slug": slug})
    return redirect(f"{detail_url}?posted=1#forecasts")


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


def _creator_program_enabled(user):
    from accounts.monetization_selectors import get_creator_program_or_none

    program = get_creator_program_or_none(user)
    return program is not None and program.is_enabled


@login_required
@require_http_methods(["GET", "POST"])
def create_prediction_view(request, slug):
    market = get_object_or_404(Market, slug=slug)
    existing = get_user_active_prediction(request.user, market)
    creator_enabled = _creator_program_enabled(request.user)

    if request.method == "POST":
        if existing:
            messages.error(request, build_duplicate_forecast_error(user=request.user, market=market))
            anchor = _forecast_form_anchor(market)
            return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}{anchor}")

        form = ForecastForm(
            request.POST,
            market=market,
            creator_program_enabled=creator_enabled,
        )
        if form.is_valid():
            try:
                create_prediction(
                    user=request.user,
                    market=market,
                    predicted_outcome=form.cleaned_data["predicted_outcome"],
                    predicted_direction=form.cleaned_data["predicted_direction"],
                    reasoning=form.cleaned_data.get("reasoning", ""),
                    audience=form.cleaned_audience_value(),
                )
            except (ValueError, ValidationError, ContentRejected) as exc:
                messages.error(request, write_guard_user_message(exc))
                return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}{_forecast_form_anchor(market)}")
            except abuse_services.RateLimitExceeded as exc:
                messages.error(request, write_guard_user_message(exc))
                return redirect(f"{reverse('markets:detail', kwargs={'slug': slug})}{_forecast_form_anchor(market)}")
            messages.success(request, _("Your forecast was posted."))
            return _forecast_success_redirect(request, slug=slug)
    else:
        form = (
            ForecastForm(market=market, creator_program_enabled=creator_enabled)
            if not existing
            else None
        )

    return_url = resolve_market_return_url(request, slug=slug)

    return render(
        request,
        "predictions/prediction_form.html",
        {
            "form": form,
            "market": market,
            "existing": existing,
            "creator_program_enabled": creator_enabled,
            "return_url": return_url,
        },
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


def prediction_detail(request, prediction_id):
    """Public, shareable forecast card page (works logged-out for virality)."""
    prediction = get_object_or_404(
        Prediction.objects.select_related("user", "user__profile", "market"),
        pk=prediction_id,
    )
    metrics = build_forecast_card_metrics(prediction)
    return render(
        request,
        "predictions/prediction_detail.html",
        {
            "prediction": prediction,
            "market": prediction.market,
            "metrics": metrics,
            "share_url": request.build_absolute_uri(
                reverse("prediction_card", args=[prediction.id])
            ),
        },
    )


def prediction_og_image(request, prediction_id):
    """PNG share image for the forecast card (Open Graph / link previews)."""
    from django.http import HttpResponse

    from predictions.og_images import get_prediction_og_image

    prediction = get_object_or_404(
        Prediction.objects.select_related("user", "market"),
        pk=prediction_id,
    )
    metrics = build_forecast_card_metrics(prediction)
    png_bytes = get_prediction_og_image(prediction, metrics)
    response = HttpResponse(png_bytes, content_type="image/png")
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_POST
def prediction_share(request, prediction_id):
    """Record a share click (popularity only, deduped + capped in the service)."""
    from django.http import JsonResponse

    from reputation.popularity_services import record_prediction_share

    prediction = get_object_or_404(
        Prediction.objects.select_related("user", "user__profile"),
        pk=prediction_id,
    )
    viewer = request.user if request.user.is_authenticated else None
    event = record_prediction_share(prediction=prediction, viewer=viewer)
    return JsonResponse({"recorded": event is not None})


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
