from django.core.management.base import BaseCommand

from integrations.services import import_markets_from_kalshi, sync_kalshi_markets_by_series


class Command(BaseCommand):
    help = "Import markets from Kalshi (read-only, no trading)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument(
            "--status",
            type=str,
            default="open",
            help="Kalshi market status filter (open, closed, settled, etc.)",
        )
        parser.add_argument(
            "--series-ticker",
            type=str,
            default="",
            help="Import markets for a Kalshi series ticker (e.g. KXHIGHNY)",
        )
        parser.add_argument(
            "--category-name",
            type=str,
            default="",
            help="Default category label when using --series-ticker",
        )
        parser.add_argument(
            "--include-mve",
            action="store_true",
            help="Include multivariate (combo) markets",
        )

    def handle(self, *args, **options):
        if options["series_ticker"]:
            category_name = options["category_name"] or options["series_ticker"]
            result = sync_kalshi_markets_by_series(
                series_ticker=options["series_ticker"],
                default_category=category_name,
                limit=options["limit"],
                status=options["status"],
                exclude_mve=not options["include_mve"],
            )
        else:
            result = import_markets_from_kalshi(
                limit=options["limit"],
                status=options["status"],
                exclude_mve=not options["include_mve"],
            )

        created = sum(1 for item in result["imported"] if item["created"])
        updated = len(result["imported"]) - created
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(result['imported'])} markets ({created} new, {updated} updated)"
            )
        )
        if result["errors"]:
            self.stdout.write(
                self.style.WARNING(f"{len(result['errors'])} errors during import")
            )
