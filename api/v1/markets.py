"""Market serializers and viewsets for API v1."""

from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from api.permissions import HasApiScope, IsReadOnlyOrAuthenticated
from api.serializers import PublicUsernameMixin
from markets.models import Market
from markets.pagination import MarketApiPagination, resolve_markets_list_status
from markets.selectors import discoverable_market_q, get_markets_for_display, get_markets_list


class MarketListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    is_forecastable = serializers.SerializerMethodField()
    outcomes = serializers.SerializerMethodField()

    class Meta:
        model = Market
        fields = (
            "id",
            "slug",
            "title",
            "category",
            "canonical_category_slug",
            "status",
            "source",
            "close_date",
            "is_forecastable",
            "outcomes",
            "current_probability",
            "created_at",
        )

    def get_title(self, obj):
        return getattr(obj, "display_title", None) or obj.title

    def get_is_forecastable(self, obj):
        return obj.is_forecastable

    def get_outcomes(self, obj):
        return obj.outcome_labels


class MarketDetailSerializer(MarketListSerializer):
    class Meta(MarketListSerializer.Meta):
        fields = MarketListSerializer.Meta.fields + (
            "external_id",
            "description",
            "resolution_date",
            "resolved_outcome",
            "polymarket_slug",
            "polymarket_synced_at",
            "updated_at",
        )


class MarketRawDetailSerializer(MarketDetailSerializer):
    class Meta(MarketDetailSerializer.Meta):
        fields = MarketDetailSerializer.Meta.fields + (
            "polymarket_raw",
            "polymarket_event_raw",
        )


class MarketViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = "slug"
    permission_classes = [IsReadOnlyOrAuthenticated]
    pagination_class = MarketApiPagination

    def _include_raw_requested(self):
        return self.request.query_params.get("include_raw") in {"1", "true", "yes"}

    def get_serializer_class(self):
        if self.action == "retrieve":
            if self._include_raw_requested():
                user = self.request.user
                if not user or not user.is_authenticated or not user.is_staff:
                    raise PermissionDenied("include_raw is restricted to staff accounts.")
                return MarketRawDetailSerializer
            return MarketDetailSerializer
        return MarketListSerializer

    def get_queryset(self):
        status, _ = resolve_markets_list_status(self.request)
        category = self.request.query_params.get("category")
        search = self.request.query_params.get("q")
        forecastable_only = self.request.query_params.get("forecastable") in {
            "1",
            "true",
            "yes",
        }
        source = self.request.query_params.get("source")
        limit = self.request.query_params.get("limit")
        if limit is not None:
            try:
                limit = min(int(limit), 100)
            except (TypeError, ValueError):
                limit = None
            markets = get_markets_for_display(
                status=status,
                category=category,
                search=search or None,
                source=source,
                limit=limit or 25,
            )
            if forecastable_only:
                markets = [m for m in markets if m.is_forecastable]
            return Market.objects.filter(pk__in=[m.pk for m in markets]).order_by("-created_at")

        qs = get_markets_list(status=status, category=category, search=search)
        if forecastable_only:
            qs = qs.filter(discoverable_market_q())
        if source:
            qs = qs.filter(source=source)
        return qs
