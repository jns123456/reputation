"""Forecast debrief (post-resolution reflection) services.

Debriefs are owner-authored, write-once, and popularity-only — they never
affect reputation (§6). Distinct from ``Prediction.reasoning`` (pre-forecast thesis).
"""

from django.db import transaction
from django.utils.translation import gettext as _

from predictions.models import ForecastDebrief, Prediction
from reputation.models import PopularityEvent
from reputation.popularity_services import record_popularity_event

DEBRIEF_MIN_CHARS = 20
DEBRIEF_MAX_CHARS = 1000


class DebriefError(ValueError):
    """Raised when a debrief cannot be created."""


def create_forecast_debrief(*, prediction, user, body: str) -> ForecastDebrief:
    """Create an immutable postmortem for a resolved forecast.

    Only the forecast owner may write one, and only after resolution. A second
    attempt raises ``DebriefError`` — debriefs are not editable.
    """
    from accounts.write_guard import guard_write_action

    cleaned = (body or "").strip()
    if len(cleaned) < DEBRIEF_MIN_CHARS:
        raise DebriefError(
            _("Write at least %(min)s characters for your debrief.")
            % {"min": DEBRIEF_MIN_CHARS}
        )
    if len(cleaned) > DEBRIEF_MAX_CHARS:
        raise DebriefError(
            _("Debriefs must be %(max)s characters or fewer.")
            % {"max": DEBRIEF_MAX_CHARS}
        )

    guard_write_action(
        action="debrief",
        user=user,
        text=cleaned,
        content_scope="write:debrief",
    )

    if prediction.user_id != user.id:
        raise DebriefError(_("You can only write a debrief on your own forecast."))
    if prediction.status != Prediction.Status.RESOLVED:
        raise DebriefError(_("Debriefs are only available after a forecast resolves."))
    if ForecastDebrief.objects.filter(prediction=prediction).exists():
        raise DebriefError(_("You already published a debrief for this forecast."))

    with transaction.atomic():
        debrief = ForecastDebrief.objects.create(
            prediction=prediction,
            user=user,
            body=cleaned,
        )
        record_popularity_event(
            user=user,
            points_delta=0,
            event_type=PopularityEvent.EventType.DEBRIEF_POSTED,
            reason=f"Posted forecast debrief on {prediction.market.title}",
            prediction=prediction,
        )

    from accounts.streak_services import record_activity

    record_activity(user)
    return debrief


def get_debrief_for_prediction(prediction) -> ForecastDebrief | None:
    """Return the debrief if present, using the reverse OneToOne when cached."""
    try:
        return prediction.debrief
    except ForecastDebrief.DoesNotExist:
        return None
