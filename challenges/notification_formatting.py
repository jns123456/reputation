def _format_rep_points(points):
    return f"+{points}" if points >= 0 else str(points)


def _build_standings_summary(standings):
    parts = []
    for row in standings[:4]:
        name = row["participant"].user.public_name
        parts.append(f"{row['rank']}. {name} {_format_rep_points(row['reputation_points'])}")
    summary = " · ".join(parts)
    if len(standings) > 4:
        summary += f" · +{len(standings) - 4} more"
    return summary
