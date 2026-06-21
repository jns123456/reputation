from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from integrations.polymarket.urls import resolve_polymarket_public_url
from markets.categories import resolve_market_category_slug


class Market(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")
        RESOLVED = "resolved", _("Resolved")

    class Source(models.TextChoices):
        POLYMARKET = "polymarket", "Polymarket"
        MANUAL = "manual", "Manual"

    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    title_es = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    description_es = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    canonical_category_slug = models.CharField(max_length=50, blank=True, db_index=True)
    # Denormalized browse-area membership (computed from raw payloads at save
    # time) so request-time filtering/counting avoids N+1 on deferred JSON.
    browse_area_slugs = models.JSONField(default=list, blank=True)
    slug = models.SlugField(max_length=550, unique=True)
    source = models.CharField(
        max_length=50,
        choices=Source.choices,
        default=Source.POLYMARKET,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    outcomes = models.JSONField(default=list)
    current_probability = models.JSONField(default=dict, blank=True)
    close_date = models.DateTimeField(null=True, blank=True)
    resolution_date = models.DateTimeField(null=True, blank=True)
    resolved_outcome = models.CharField(max_length=255, blank=True)
    # Mirrors Polymarket's real-time order gate: when the source stops accepting
    # orders (event started, suspended, or resolving) we stop accepting forecasts,
    # even if the imported ``status`` is still a stale ``open``.
    accepting_orders = models.BooleanField(default=True, db_index=True)
    # Scheduled start of the underlying event (e.g. a tennis/soccer match). Kept
    # for context and future live-event handling; sourced from Polymarket
    # ``gameStartTime`` / event ``startDate`` when available.
    game_start_time = models.DateTimeField(null=True, blank=True)
    polymarket_slug = models.SlugField(max_length=550, blank=True, db_index=True)
    polymarket_raw = models.JSONField(default=dict, blank=True)
    polymarket_event_raw = models.JSONField(default=dict, blank=True)
    polymarket_synced_at = models.DateTimeField(null=True, blank=True)
    volume_total = models.FloatField(default=0.0, db_index=True)
    volume_24h = models.FloatField(default=0.0, db_index=True)
    liquidity_total = models.FloatField(default=0.0, db_index=True)
    card_image_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "canonical_category_slug"]),
        ]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self) -> str:
        if get_language() == "es" and self.title_es:
            return self.title_es
        return self.title

    @property
    def display_description(self) -> str:
        if get_language() == "es" and self.description_es:
            return self.description_es
        return self.description

    @property
    def display_category(self) -> str:
        from markets.localization import localize_category_label

        return localize_category_label(self.category)

    @property
    def display_source(self) -> str:
        if self.source == self.Source.POLYMARKET:
            return _("Polymarket")
        return _("Market")

    def save(self, *args, **kwargs):
        from markets.browse_areas import compute_browse_area_slugs

        self.canonical_category_slug = resolve_market_category_slug(self)
        self.browse_area_slugs = compute_browse_area_slugs(self)
        if not self.slug:
            base = slugify(self.title)[:500] or "market"
            slug = base
            counter = 1
            while Market.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    @property
    def is_expired(self):
        """True when the close date has already passed.

        Polymarket data is refreshed asynchronously, so a market can still be
        ``OPEN`` locally for hours after it actually closed upstream. Comparing
        ``close_date`` to now lets us treat those stale rows as no longer
        forecastable without waiting for the next sync.
        """
        if not self.close_date:
            return False
        return self.close_date <= timezone.now()

    @property
    def is_in_play(self):
        """True once the underlying event has started.

        For live events (tennis/soccer) the outcome is revealed in real time, so
        forecasting closes at kickoff. This is a local, network-free backstop
        that holds even when the source's ``accepting_orders`` flag has not yet
        synced — directly closing the sync-delay window for sports.
        """
        if not self.game_start_time:
            return False
        return self.game_start_time <= timezone.now()

    @property
    def is_forecastable(self):
        """Whether a new forecast may be created on this market.

        Mirrors Polymarket's real-time order gate (``accepting_orders``) and adds
        local, network-free backstops that hold when our imported data lags the
        source: ``OPEN`` status, a future ``close_date``, and — for live events —
        a kickoff that has not passed (``is_in_play``).
        """
        return (
            self.is_open
            and not self.is_expired
            and self.accepting_orders
            and not self.is_in_play
        )

    @property
    def is_exitable(self):
        """Whether an existing pending forecast may be closed early.

        Exits only require the market to remain ``OPEN`` locally — users may
        realize mark-to-market reputation even when new forecasts are blocked
        (expired close date, source stopped accepting orders, event in play).
        """
        return self.is_open

    @property
    def polymarket_url(self):
        return resolve_polymarket_public_url(self)

    @property
    def polymarket_market_url(self):
        from integrations.polymarket.urls import resolve_polymarket_market_url

        return resolve_polymarket_market_url(self)

    @property
    def has_polymarket_data(self):
        return bool(self.polymarket_raw)

    @property
    def outcome_labels(self):
        if isinstance(self.outcomes, list):
            return [o.get("label", o) if isinstance(o, dict) else str(o) for o in self.outcomes]
        return []

    @property
    def is_soccer_match(self):
        from integrations.polymarket.soccer_matches import is_world_cup_match_market

        return is_world_cup_match_market(self)

    @property
    def is_h2h_match(self):
        from integrations.polymarket.head_to_head_matches import is_h2h_match_market

        return is_h2h_match_market(self)

    def _match_team_names(self):
        if self._card_payloads_deferred():
            labels = self.outcome_labels
        else:
            raw = self.polymarket_raw or {}
            team_a = raw.get("team_a") or ""
            team_b = raw.get("team_b") or ""
            if team_a and team_b:
                return team_a, team_b
            labels = self.outcome_labels

        if len(labels) >= 3 and str(labels[1]).strip().lower() == "draw":
            return str(labels[0]), str(labels[2])
        if len(labels) == 2 and {str(label).strip().lower() for label in labels} != {"yes", "no"}:
            return str(labels[0]), str(labels[1])
        return "", ""

    @property
    def match_team_a(self):
        return self._match_team_names()[0]

    @property
    def match_team_b(self):
        return self._match_team_names()[1]

    def _team_outcome_icon(self, team_label: str) -> str:
        if not team_label:
            return ""
        for outcome in self.outcomes or []:
            if isinstance(outcome, dict) and outcome.get("label") == team_label:
                icon = outcome.get("icon") or ""
                if icon:
                    return icon
        if self._card_payloads_deferred():
            return ""
        raw = self.polymarket_raw or {}
        if team_label == raw.get("team_a"):
            return raw.get("team_a_icon") or ""
        if team_label == raw.get("team_b"):
            return raw.get("team_b_icon") or ""
        return ""

    @property
    def match_team_a_icon(self) -> str:
        return self._team_outcome_icon(self.match_team_a)

    @property
    def match_team_b_icon(self) -> str:
        return self._team_outcome_icon(self.match_team_b)

    @property
    def forecast_mode(self) -> str:
        from markets.forecast_modes import get_forecast_mode

        return get_forecast_mode(self)

    @property
    def is_multi_binary_market(self) -> bool:
        from markets.forecast_modes import uses_multi_binary_panel

        return uses_multi_binary_panel(self)

    @property
    def kickoff_at(self):
        if self.game_start_time:
            return self.game_start_time
        raw = self.polymarket_raw or {}
        kickoff = raw.get("kickoff_at")
        if not kickoff:
            return self.close_date
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(str(kickoff))
        if parsed is None:
            return self.close_date
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.utc)
        return parsed

    # Large JSON payloads deferred by ``market_card_queryset`` for list/grid views.
    _CARD_DEFERRED_PAYLOAD_FIELDS = frozenset(
        {
            "polymarket_raw",
            "polymarket_event_raw",
        }
    )

    def _card_payloads_deferred(self) -> bool:
        """True when raw payloads were deferred (list/grid querysets).

        Accessing a deferred field triggers a per-row DB fetch (N+1). On card
        querysets the denormalized columns are authoritative, so callers should
        avoid the payload fallback entirely.
        """
        return bool(self._CARD_DEFERRED_PAYLOAD_FIELDS & self.get_deferred_fields())

    @property
    def image_url(self):
        """Market/event image from denormalized field or import payload."""
        if self.card_image_url:
            return self.card_image_url
        if self._card_payloads_deferred():
            return ""
        from markets.display_metadata import extract_card_image_url_from_market

        return extract_card_image_url_from_market(self)

    @property
    def volume_label(self):
        """Human-readable volume string for card footers."""
        from markets.display_metadata import format_volume_label, market_volume_for_sort

        return format_volume_label(market_volume_for_sort(self))

    @property
    def expiration_countdown(self):
        """
        Days until (or since) market close for UI countdowns.

        Returns dict with keys: text, days (signed), tone (normal|soon|urgent|past|resolved).
        None when no close_date is available.
        """
        if self.status == self.Status.RESOLVED:
            return {
                "text": _("Resolved"),
                "days": 0,
                "tone": "resolved",
            }

        if not self.close_date:
            return None

        days = (self.close_date.date() - timezone.now().date()).days

        if days > 1:
            tone = "urgent" if days <= 7 else "normal"
            return {
                "text": ngettext("%(days)s day left", "%(days)s days left", days) % {"days": days},
                "days": days,
                "tone": tone,
            }
        if days == 1:
            return {"text": _("1 day left"), "days": 1, "tone": "soon"}
        if days == 0:
            return {"text": _("Ends today"), "days": 0, "tone": "urgent"}
        past = abs(days)
        if past == 1:
            text = _("Ended yesterday")
        else:
            text = ngettext("Ended %(past)s day ago", "Ended %(past)s days ago", past) % {"past": past}
        return {"text": text, "days": days, "tone": "past"}
