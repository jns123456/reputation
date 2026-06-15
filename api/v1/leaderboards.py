"""Leaderboard API views."""

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.selectors import get_top_popular_users, get_top_predictors
from api.permissions import IsReadOnlyOrAuthenticated
from reputation.leaderboard import build_leaderboard_rows
from reputation.ranking_modes import ABSOLUTE, normalize_reputation_ranking_mode


class ReputationLeaderboardView(APIView):
    permission_classes = [IsReadOnlyOrAuthenticated]

    def get(self, request):
        mode = normalize_reputation_ranking_mode(request.query_params.get("mode"))
        limit = min(int(request.query_params.get("limit", 50) or 50), 100)
        rows = get_top_predictors(limit, mode=mode)
        leaderboard_rows = build_leaderboard_rows(rows, ranking_mode=mode)
        return Response(
            {
                "ranking_mode": mode,
                "results": [
                    {
                        "rank": row["rank"],
                        "qualifies_for_relative_ranking": row["qualifies_relative"],
                        "username": (
                            row["stats"].user.username
                            if row["stats"].user.show_username_publicly
                            else None
                        ),
                        "display_name": row["stats"].user.public_name,
                        "reputation_points": row["stats"].reputation_points,
                        "reputation_score": row["stats"].reputation_score,
                        "scored_forecast_count": row["stats"].scored_forecast_count,
                    }
                    for row in leaderboard_rows
                ],
            }
        )


class AbsoluteReputationLeaderboardView(ReputationLeaderboardView):
    def get(self, request):
        request.GET._mutable = True
        request.GET["mode"] = ABSOLUTE
        return super().get(request)


class PopularityLeaderboardView(APIView):
    permission_classes = [IsReadOnlyOrAuthenticated]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 50) or 50), 100)
        rows = get_top_popular_users(limit)
        return Response(
            {
                "results": [
                    {
                        "rank": i + 1,
                        "username": p.user.username if p.user.show_username_publicly else None,
                        "display_name": p.user.public_name,
                        "popularity_points": p.popularity_points,
                        "popularity_score": p.popularity_score,
                    }
                    for i, p in enumerate(rows)
                ]
            }
        )
