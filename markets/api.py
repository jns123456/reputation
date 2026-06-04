from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from markets.models import Market
from markets.selectors import get_markets_list


class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Market
        fields = (
            "id",
            "external_id",
            "title",
            "description",
            "category",
            "slug",
            "source",
            "status",
            "outcomes",
            "current_probability",
            "close_date",
            "resolution_date",
            "resolved_outcome",
            "created_at",
        )


class MarketDetailSerializer(MarketSerializer):
    """Detail payload without large raw Polymarket API responses by default."""

    class Meta(MarketSerializer.Meta):
        fields = MarketSerializer.Meta.fields + (
            "polymarket_slug",
            "polymarket_synced_at",
            "updated_at",
        )


class MarketRawDetailSerializer(MarketDetailSerializer):
    """Opt-in debug/integration payload including raw Polymarket responses."""

    class Meta(MarketDetailSerializer.Meta):
        fields = MarketDetailSerializer.Meta.fields + (
            "polymarket_raw",
            "polymarket_event_raw",
        )


class MarketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Market.objects.all()
    serializer_class = MarketSerializer
    lookup_field = "slug"

    def _include_raw_requested(self):
        return self.request.query_params.get("include_raw") in {"1", "true", "yes"}

    def get_serializer_class(self):
        if self.action == "retrieve":
            if self._include_raw_requested():
                user = self.request.user
                if not user or not user.is_authenticated or not user.is_staff:
                    raise PermissionDenied(
                        "include_raw is restricted to staff accounts."
                    )
                return MarketRawDetailSerializer
            return MarketDetailSerializer
        return MarketSerializer

    def get_queryset(self):
        status = self.request.query_params.get("status")
        category = self.request.query_params.get("category")
        search = self.request.query_params.get("q")
        return get_markets_list(
            status=status,
            category=category,
            search=search,
        )
