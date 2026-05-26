from django.core.management.base import BaseCommand

from integrations.sync import refresh_stale_open_markets, sync_all_category_markets
from integrations.services import (
    import_markets_from_kalshi,
    import_markets_from_polymarket,
    refresh_kalshi_market_images,
)
from markets.source_filters import kalshi_enabled


class Command(BaseCommand):
    help = "Sync markets from Polymarket and Kalshi (read-only, no trading)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--categories",
            action="store_true",
            help="Sync all canonical browse categories from configured sources",
        )
        parser.add_argument(
            "--stale",
            action="store_true",
            help="Refresh open markets that have not synced recently",
        )
        parser.add_argument(
            "--kalshi-discovery",
            action="store_true",
            help="Import newly listed open Kalshi markets",
        )
        parser.add_argument(
            "--polymarket",
            action="store_true",
            help="Import open markets from Polymarket",
        )
        parser.add_argument(
            "--kalshi-images",
            action="store_true",
            help="Refresh Kalshi event metadata (team/event images for cards)",
        )
        parser.add_argument(
            "--if-due",
            action="store_true",
            help="Run category + stale sync only when MARKET_FULL_SYNC_INTERVAL_HOURS has elapsed",
        )
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        if options["if_due"]:
            from integrations.market_sync_scheduler import run_scheduled_market_sync

            result = run_scheduled_market_sync(force=False)
            if result is None:
                self.stdout.write("Scheduled sync not due yet.")
                return
            self._print_summary("Category sync", result["categories"])
            stale = result["stale"]
            self.stdout.write(
                self.style.SUCCESS(
                    f"Stale refresh: {stale['refreshed']} refreshed ({stale['failures']} failures)"
                )
            )
            return

        if options["categories"]:
            result = sync_all_category_markets(limit=options["limit"])
            from integrations.market_sync_scheduler import record_full_sync_run

            record_full_sync_run()
            self._print_summary("Category sync", result)
            return

        if options["stale"]:
            result = refresh_stale_open_markets()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Refreshed {result['refreshed']} stale markets "
                    f"({result['failures']} failures)"
                )
            )
            return

        if options["kalshi_discovery"]:
            if not kalshi_enabled():
                self.stdout.write(self.style.WARNING("Kalshi is disabled (KALSHI_ENABLED=False)."))
                return
            result = import_markets_from_kalshi(limit=options["limit"])
            self._print_import_result("Kalshi discovery", result)
            return

        if options["polymarket"]:
            result = import_markets_from_polymarket(limit=options["limit"])
            self._print_import_result("Polymarket import", result)
            return

        if options["kalshi_images"]:
            if not kalshi_enabled():
                self.stdout.write(self.style.WARNING("Kalshi is disabled (KALSHI_ENABLED=False)."))
                return
            result = refresh_kalshi_market_images(batch_size=options["limit"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Kalshi images: {result['refreshed']} markets updated "
                    f"({result['failures']} failures)"
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                "No action selected. Use --categories, --if-due, --stale, --kalshi-discovery, "
                "--kalshi-images, or --polymarket."
            )
        )

    def _print_import_result(self, label, result):
        created = sum(1 for item in result["imported"] if item["created"])
        updated = len(result["imported"]) - created
        self.stdout.write(
            self.style.SUCCESS(
                f"{label}: {len(result['imported'])} markets ({created} new, {updated} updated)"
            )
        )
        if result["errors"]:
            self.stdout.write(self.style.WARNING(f"{len(result['errors'])} errors"))

    def _print_summary(self, label, result):
        self.stdout.write(
            self.style.SUCCESS(
                f"{label}: {result['imported']} imported, {result['updated']} updated"
            )
        )
        if result["errors"]:
            self.stdout.write(self.style.WARNING(f"{len(result['errors'])} errors"))
