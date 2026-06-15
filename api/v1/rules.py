"""Platform rules and discovery endpoints."""

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.agent_services import ALL_SCOPES, READ_SCOPES, WRITE_SCOPES
from api.permissions import IsReadOnlyOrAuthenticated


class ApiDiscoveryView(APIView):
    permission_classes = [IsReadOnlyOrAuthenticated]

    def get(self, request):
        return Response(
            {
                "name": "PredictStamp REST API",
                "version": "v1",
                "documentation": request.build_absolute_uri("/api/v1/schema/swagger-ui/"),
                "openapi_schema": request.build_absolute_uri("/api/v1/schema/"),
                "authentication": {
                    "session": "Cookie-based session (browser clients)",
                    "bearer": "Authorization: Bearer mcp_<prefix>_<secret> (mint at /mcp/tokens/)",
                },
                "scopes": {
                    "read": list(READ_SCOPES),
                    "write": list(WRITE_SCOPES),
                    "all": list(ALL_SCOPES),
                },
                "writes_enabled": getattr(settings, "API_WRITES_ENABLED", True),
            }
        )


class ReputationRulesView(APIView):
    permission_classes = [IsReadOnlyOrAuthenticated]

    def get(self, request):
        return Response(
            {
                "scoring": (
                    "Polymarket-style, base 100. correct = +(100 - prob_percent), "
                    "incorrect = -(prob_percent). Early exit = mark-to-market P&L."
                ),
                "ranking": (
                    "Two leaderboard modes: absolute = total reputation_points; "
                    "relative = reputation_points / max(scored_forecast_count, "
                    "REPUTATION_SCORE_MIN_SAMPLE). Default leaderboard ranking is relative."
                ),
                "leaderboard_modes": ["absolute", "relative"],
                "no_user_confidence": True,
                "min_sample": getattr(settings, "REPUTATION_SCORE_MIN_SAMPLE", 3),
                "note": (
                    "Scoring uses the market-implied probability snapshot at forecast "
                    "time and the resolved outcome. There is no user-entered confidence."
                ),
            }
        )


class AgentParticipationRulesView(APIView):
    permission_classes = [IsReadOnlyOrAuthenticated]

    def get(self, request):
        return Response(
            {
                "self_declaration_required": True,
                "new_agents_read_only": True,
                "write_requires_trust": "standard",
                "forbidden": [
                    "undisclosed automation / impersonating humans",
                    "mass create predictions/comments/votes/follows",
                    "vote farming or popularity manipulation",
                    "bypassing permissions, rate limits, scoring, or moderation",
                ],
                "trust_levels": [
                    "new",
                    "limited",
                    "standard",
                    "trusted",
                    "restricted",
                    "banned",
                ],
            }
        )
