from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from integrations.polymarket.urls import resolve_polymarket_public_url


class Market(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        RESOLVED = "resolved", "Resolved"

    class Source(models.TextChoices):
        POLYMARKET = "polymarket", "Polymarket"
        MANUAL = "manual", "Manual"

    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
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
    def outcome_labels(self):
        if isinstance(self.outcomes, list):
            return [o.get("label", o) if isinstance(o, dict) else str(o) for o in self.outcomes]
        return []

    @property
    def image_url(self):
        """Market/event image from Polymarket import payload."""
        raw = self.polymarket_raw or {}
        event = self.polymarket_event_raw or {}
        return (
            raw.get("image")
            or raw.get("icon")
            or event.get("image")
            or event.get("icon")
            or ""
        )

    @property
    def volume_label(self):
        """Human-readable volume string for card footers."""
        raw = self.polymarket_raw or {}
        event = self.polymarket_event_raw or {}
        for source in (raw, event):
            for key in ("volumeNum", "volume", "volume24hr"):
                value = source.get(key)
                if value is None or value == "":
                    continue
                try:
                    amount = float(value)
                except (TypeError, ValueError):
                    continue
                if amount >= 1_000_000:
                    return f"${amount / 1_000_000:.1f}M Vol."
                if amount >= 1_000:
                    return f"${amount / 1_000:.0f}K Vol."
                return f"${amount:.0f} Vol."
        return ""

    @property
    def expiration_countdown(self):
        """
        Days until (or since) market close for UI countdowns.

        Returns dict with keys: text, days (signed), tone (normal|soon|urgent|past|resolved).
        None when no close_date is available.
        """
        if self.status == self.Status.RESOLVED:
            return {
                "text": "Resolved",
                "days": 0,
                "tone": "resolved",
            }

        if not self.close_date:
            return None

        days = (self.close_date.date() - timezone.now().date()).days

        if days > 1:
            tone = "urgent" if days <= 7 else "normal"
            return {
                "text": f"{days} days left",
                "days": days,
                "tone": tone,
            }
        if days == 1:
            return {"text": "1 day left", "days": 1, "tone": "soon"}
        if days == 0:
            return {"text": "Ends today", "days": 0, "tone": "urgent"}
        past = abs(days)
        if past == 1:
            text = "Ended yesterday"
        else:
            text = f"Ended {past} days ago"
        return {"text": text, "days": days, "tone": "past"}
