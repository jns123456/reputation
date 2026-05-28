"""Backfill Spanish title/description for imported markets."""

from django.core.management.base import BaseCommand
from django.db.models import Q

from markets.models import Market
from markets.translation_services import apply_spanish_translations_to_defaults, translation_enabled


class Command(BaseCommand):
    help = "Translate imported market titles and descriptions into Spanish."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=["polymarket", "kalshi", "all"],
            default="polymarket",
            help="Which imported markets to translate.",
        )
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Only translate markets missing Spanish title or description.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum markets to process (0 = no limit).",
        )

    def handle(self, *args, **options):
        if not translation_enabled():
            self.stderr.write(
                self.style.ERROR(
                    "MARKET_TRANSLATION_ENABLED is False — enable it in settings/.env first."
                )
            )
            return

        queryset = Market.objects.exclude(source=Market.Source.MANUAL).order_by("-updated_at")
        source = options["source"]
        if source != "all":
            queryset = queryset.filter(source=source)

        if options["missing_only"]:
            queryset = queryset.filter(Q(description_es="") | Q(title_es=""))

        limit = options["limit"]
        if limit:
            queryset = queryset[:limit]

        updated = 0
        for market in queryset.iterator():
            defaults = {
                "title": market.title,
                "description": market.description,
            }
            apply_spanish_translations_to_defaults(defaults, existing_market=market)
            fields = []
            if defaults.get("title_es") != market.title_es:
                market.title_es = defaults.get("title_es", "")
                fields.append("title_es")
            if defaults.get("description_es") != market.description_es:
                market.description_es = defaults.get("description_es", "")
                fields.append("description_es")
            if fields:
                fields.append("updated_at")
                market.save(update_fields=fields)
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Translated {updated} market(s)."))
