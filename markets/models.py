from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from integrations.kalshi.urls import resolve_kalshi_public_url
from integrations.polymarket.urls import resolve_polymarket_public_url
from markets.categories import resolve_market_category_slug


class Market(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        CLOSED = "closed", _("Closed")
        RESOLVED = "resolved", _("Resolved")

    class Source(models.TextChoices):
        POLYMARKET = "polymarket", "Polymarket"
        KALSHI = "kalshi", "Kalshi"
        MANUAL = "manual", "Manual"

    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    canonical_category_slug = models.CharField(max_length=50, blank=True, db_index=True)
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
    polymarket_slug = models.SlugField(max_length=550, blank=True, db_index=True)
    polymarket_raw = models.JSONField(default=dict, blank=True)
    polymarket_event_raw = models.JSONField(default=dict, blank=True)
    polymarket_synced_at = models.DateTimeField(null=True, blank=True)
    kalshi_ticker = models.CharField(max_length=255, blank=True, db_index=True)
    kalshi_raw = models.JSONField(default=dict, blank=True)
    kalshi_event_raw = models.JSONField(default=dict, blank=True)
    kalshi_synced_at = models.DateTimeField(null=True, blank=True)
    volume_total = models.FloatField(default=0.0, db_index=True)
    card_image_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "canonical_category_slug"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.canonical_category_slug = resolve_market_category_slug(self)
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
    def kalshi_url(self):
        return resolve_kalshi_public_url(self)

    @property
    def has_kalshi_data(self):
        return bool(self.kalshi_raw)

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
    def kickoff_at(self):
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

    @property
    def image_url(self):
        """Market/event image from denormalized field or import payload."""
        if self.card_image_url:
            return self.card_image_url
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
