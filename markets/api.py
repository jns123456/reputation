from rest_framework import serializers, viewsets

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
    """Full market payload including raw Polymarket API responses."""

    class Meta(MarketSerializer.Meta):
        fields = MarketSerializer.Meta.fields + (
            "polymarket_slug",
            "polymarket_raw",
            "polymarket_event_raw",
            "polymarket_synced_at",
            "updated_at",
        )


class MarketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Market.objects.all()
    serializer_class = MarketSerializer
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
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
