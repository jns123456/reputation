def _format_rep_points(points):
    return f"+{points}" if points >= 0 else str(points)


def _build_standings_summary(standings):
    from django.utils.translation import gettext as _

    parts = []
    for row in standings[:4]:
        name = row["participant"].user.public_name
        parts.append(f"{row['rank']}. {name} {_format_rep_points(row['reputation_points'])}")
    summary = " · ".join(parts)
    if len(standings) > 4:
        summary += _(" · +%(count)s more") % {"count": len(standings) - 4}
    return summary
