"""Share-card context for public profile pages."""

from __future__ import annotations

from django.utils.translation import gettext as _

from reputation.platform_rank import get_user_reputation_rank_relative


def build_profile_share_context(*, user, prediction_summary) -> dict:
    profile = getattr(user, "profile", None)
    global_rank = get_user_reputation_rank_relative(profile) if profile else None
    handle = f"@{user.username}" if user.show_username_publicly else user.public_name

    parts = []
    if profile:
        parts.append(
            _("%(rep)s reputation · %(score)s per forecast")
            % {"rep": profile.reputation_points, "score": profile.reputation_score}
        )
    if prediction_summary.get("accuracy_pct") is not None:
        parts.append(
            _("%(pct)s%% accuracy on resolved forecasts")
            % {"pct": prediction_summary["accuracy_pct"]}
        )
    if global_rank:
        parts.append(_("Global rank #%(rank)s") % {"rank": global_rank})

    tagline = " · ".join(str(part) for part in parts) if parts else str(
        _("Track record on PredictStamp — no money, just reputation.")
    )

    return {
        "handle": handle,
        "global_rank": global_rank,
        "prediction_summary": prediction_summary,
        "tagline": tagline,
        "share_title": _("%(name)s on PredictStamp") % {"name": user.public_name},
        "share_text": tagline,
    }
