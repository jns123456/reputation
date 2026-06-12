"""Daily missions — habit-forming quests that reward quality engagement.

The catalog is code-defined (like ``achievement_services``); per-day progress
lives in ``UserMission``. Rewards are small POPULARITY bonuses only — missions
must never create predictive reputation (AGENTS.md §6). Progress only counts
actions that already passed the write guard / content checks, so missions
cannot become a spam pump.
"""

import logging
from dataclasses import dataclass

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# Action identifiers reported by domain services.
ACTION_PREDICTION = "prediction"
ACTION_REASONED_PREDICTION = "reasoned_prediction"
ACTION_COMMENT = "comment"
ACTION_VOTE = "vote"

REASONED_PREDICTION_MIN_CHARS = 100


@dataclass(frozen=True)
class MissionTemplate:
    code: str
    name: object  # lazy translatable
    description: object
    icon: str  # Lucide icon name
    action: str
    target: int
    reward_points: int


MISSIONS = (
    MissionTemplate(
        code="daily_forecast",
        name=_("Make a forecast"),
        description=_("Place one forecast on any open market today."),
        icon="target",
        action=ACTION_PREDICTION,
        target=1,
        reward_points=2,
    ),
    MissionTemplate(
        code="daily_thesis",
        name=_("Defend a thesis"),
        description=_("Publish a forecast with written reasoning (100+ characters)."),
        icon="pen-line",
        action=ACTION_REASONED_PREDICTION,
        target=1,
        reward_points=3,
    ),
    MissionTemplate(
        code="daily_comment",
        name=_("Join a discussion"),
        description=_("Post a comment in any forecast thread."),
        icon="message-circle",
        action=ACTION_COMMENT,
        target=1,
        reward_points=1,
    ),
    MissionTemplate(
        code="daily_engage",
        name=_("Curate the feed"),
        description=_("Vote on three forecasts or comments you find insightful."),
        icon="thumbs-up",
        action=ACTION_VOTE,
        target=3,
        reward_points=1,
    ),
)
MISSIONS_BY_CODE = {mission.code: mission for mission in MISSIONS}


def record_mission_action(user, action, *, count=1):
    """Advance today's missions matching ``action``. Never raises into callers."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    try:
        return _record_mission_action(user, action, count=count)
    except Exception:  # pragma: no cover - missions must never break an action
        logger.warning(
            "record_mission_action failed user_id=%s action=%s",
            getattr(user, "id", None),
            action,
            exc_info=True,
        )
        return []


def _record_mission_action(user, action, *, count):
    from django.db import transaction

    from accounts.models import UserMission

    today = timezone.localdate()
    completed = []
    for mission in MISSIONS:
        if mission.action != action:
            continue
        with transaction.atomic():
            row, _created = UserMission.objects.select_for_update().get_or_create(
                user=user,
                code=mission.code,
                period_date=today,
            )
            if row.completed_at is not None:
                continue
            row.progress = min(mission.target, row.progress + count)
            update_fields = ["progress", "updated_at"]
            just_completed = row.progress >= mission.target
            if just_completed:
                row.completed_at = timezone.now()
                update_fields.append("completed_at")
            row.save(update_fields=update_fields)
        if just_completed:
            _award_mission_reward(user, mission)
            completed.append(mission.code)
    return completed


def _award_mission_reward(user, mission):
    from reputation.models import PopularityEvent
    from reputation.popularity_services import record_popularity_event

    record_popularity_event(
        user=user,
        points_delta=mission.reward_points,
        event_type=PopularityEvent.EventType.MISSION_COMPLETED,
        reason=f"Completed daily mission: {mission.code}",
    )


def get_daily_missions(user):
    """Today's mission cards for the dashboard. Empty for anonymous users."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []

    from accounts.models import UserMission

    today = timezone.localdate()
    rows = {
        row.code: row
        for row in UserMission.objects.filter(user=user, period_date=today)
    }
    cards = []
    for mission in MISSIONS:
        row = rows.get(mission.code)
        progress = row.progress if row else 0
        cards.append(
            {
                "mission": mission,
                "progress": progress,
                "target": mission.target,
                "completed": bool(row and row.completed_at),
                "progress_percent": int(min(100, progress * 100 / mission.target)),
            }
        )
    return cards
