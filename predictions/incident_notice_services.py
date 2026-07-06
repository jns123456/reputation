"""One-time login notices for platform incidents affecting specific forecasts."""

from __future__ import annotations

from django.utils.translation import gettext as _

from predictions.models import Prediction

F1_PODIUM_INCIDENT_ID = "f1_british_gp_podium_2026_07"
F1_PODIUM_MARKET_SLUG = "f1-british-grand-prix-driver-podium-2026-07-05"
F1_PODIUM_INCIDENT_SESSION_KEY = "f1_podium_incident_notice"
F1_PODIUM_INCIDENT_PENDING_CACHE = "f1_podium_incident_pending:{user_id}"
F1_PODIUM_INCIDENT_DISMISS_CACHE = "f1_podium_incident_dismissed:{user_id}"


def _pending_cache_key(user_id):
    return F1_PODIUM_INCIDENT_PENDING_CACHE.format(user_id=user_id)


def _dismiss_cache_key(user_id):
    return F1_PODIUM_INCIDENT_DISMISS_CACHE.format(user_id=user_id)


def user_dismissed_f1_podium_incident_notice(user) -> bool:
    from django.core.cache import cache

    if not user or not user.is_authenticated:
        return False
    return bool(cache.get(_dismiss_cache_key(user.id)))


def dismiss_f1_podium_incident_notice(*, user):
    from django.core.cache import cache

    cache.set(_dismiss_cache_key(user.id), True, timeout=None)


def is_f1_podium_leclerc_prediction(prediction) -> bool:
    if prediction.predicted_direction != Prediction.Direction.YES:
        return False
    outcome = (prediction.predicted_outcome or "").strip().lower()
    if "leclerc" not in outcome:
        return False
    market = prediction.market
    slug = (market.polymarket_slug or "").strip().lower()
    if slug == F1_PODIUM_MARKET_SLUG:
        return True
    external_id = (market.external_id or "").strip().lower()
    return external_id.endswith(F1_PODIUM_MARKET_SLUG)


def f1_podium_leclerc_predictions(*, user):
    return (
        Prediction.objects.filter(
            user=user,
            market__polymarket_slug=F1_PODIUM_MARKET_SLUG,
            status=Prediction.Status.RESOLVED,
            predicted_direction=Prediction.Direction.YES,
            predicted_outcome__icontains="leclerc",
        )
        .select_related("market")
        .order_by("-resolved_at", "-id")
    )


def _build_notice_payload(*, user, prediction=None):
    prediction = prediction or f1_podium_leclerc_predictions(user=user).first()
    if not prediction:
        return None

    from predictions.services import prediction_is_correct_for_resolved_market

    expected_correct = prediction_is_correct_for_resolved_market(prediction.market, prediction)
    return {
        "incident_id": F1_PODIUM_INCIDENT_ID,
        "prediction_id": prediction.id,
        "market_slug": prediction.market.slug,
        "market_title": prediction.market.title,
        "predicted_outcome": prediction.predicted_outcome,
        "is_correct_now": prediction.is_correct,
        "expected_correct": expected_correct,
        "dismiss_url_name": "dashboard:dismiss_f1_podium_incident_notice",
        "market_url_name": "markets:detail",
        "profile_predictions_url_name": "accounts:profile",
        "profile_username": user.username,
    }


def queue_f1_podium_incident_notice(*, user_id, prediction_id=None):
    """Cache a one-time login notice for an affected user."""
    from django.contrib.auth import get_user_model
    from django.core.cache import cache

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return False

    payload = _build_notice_payload(user=user)
    if not payload:
        return False
    if prediction_id is not None:
        payload["prediction_id"] = prediction_id

    cache.set(_pending_cache_key(user_id), payload, timeout=60 * 60 * 24 * 90)
    return True


def queue_f1_podium_incident_on_login(*, request):
    """Move cached incident alerts into the session for the next page load."""
    if not request.user.is_authenticated:
        return
    if user_dismissed_f1_podium_incident_notice(request.user):
        return
    if request.session.get(F1_PODIUM_INCIDENT_SESSION_KEY):
        return

    from django.core.cache import cache

    pending = cache.get(_pending_cache_key(request.user.id))
    if not pending:
        return
    request.session[F1_PODIUM_INCIDENT_SESSION_KEY] = pending
    cache.delete(_pending_cache_key(request.user.id))


def consume_f1_podium_incident_notice(*, request):
    """Return incident modal context once after login, if queued."""
    if not request.user.is_authenticated:
        return None
    if user_dismissed_f1_podium_incident_notice(request.user):
        request.session.pop(F1_PODIUM_INCIDENT_SESSION_KEY, None)
        return None

    payload = request.session.pop(F1_PODIUM_INCIDENT_SESSION_KEY, None)
    if not payload:
        return None

    prediction = (
        Prediction.objects.filter(
            pk=payload.get("prediction_id"),
            user=request.user,
        )
        .select_related("market")
        .first()
    )
    if prediction:
        payload = _build_notice_payload(user=request.user, prediction=prediction) or payload

    payload.setdefault("dismiss_url_name", "dashboard:dismiss_f1_podium_incident_notice")
    payload.setdefault("market_url_name", "markets:detail")
    payload.setdefault("profile_predictions_url_name", "accounts:profile")
    payload.setdefault("profile_username", request.user.username)
    return payload


def notify_f1_podium_incident_rescore(*, user_id, prediction_id):
    """Queue a login notice after a mis-scored F1 podium forecast is repaired."""
    return queue_f1_podium_incident_notice(user_id=user_id, prediction_id=prediction_id)


def backfill_f1_podium_incident_notices(*, dry_run=False):
    """Queue login notices for users affected by the F1 podium scoring incident."""
    from predictions.services import prediction_is_correct_for_resolved_market

    queued = []
    seen_users = set()
    predictions = Prediction.objects.filter(
        market__polymarket_slug=F1_PODIUM_MARKET_SLUG,
        status=Prediction.Status.RESOLVED,
        predicted_direction=Prediction.Direction.YES,
        predicted_outcome__icontains="leclerc",
    ).select_related("user", "market")

    for prediction in predictions:
        expected = prediction_is_correct_for_resolved_market(prediction.market, prediction)
        if expected is not True:
            continue
        if prediction.user_id in seen_users:
            continue
        seen_users.add(prediction.user_id)
        if user_dismissed_f1_podium_incident_notice(prediction.user):
            continue
        if dry_run:
            queued.append(
                {
                    "user_id": prediction.user_id,
                    "username": prediction.user.username,
                    "prediction_id": prediction.id,
                    "is_correct_now": prediction.is_correct,
                }
            )
            continue
        if queue_f1_podium_incident_notice(
            user_id=prediction.user_id,
            prediction_id=prediction.id,
        ):
            queued.append(prediction.user_id)

    return queued


def incident_notice_summary(*, payload):
    """Short human-readable summary for templates."""
    if not payload:
        return ""
    outcome = payload.get("predicted_outcome") or _("your pick")
    if payload.get("is_correct_now"):
        return _(
            "Your Yes on %(outcome)s for the British Grand Prix podium was correct. "
            "We fixed a scoring bug and updated your reputation."
        ) % {"outcome": outcome}
    return _(
        "Your Yes on %(outcome)s for the British Grand Prix podium should score as correct. "
        "We are fixing a scoring bug and will update your reputation."
    ) % {"outcome": outcome}
