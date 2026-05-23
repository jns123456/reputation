from django.core.management.base import BaseCommand

from integrations.services import import_markets_from_polymarket


class Command(BaseCommand):
    help = "Import markets from Polymarket (read-only, no trading)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--offset", type=int, default=0)
        parser.add_argument("--all", action="store_true", help="Include inactive markets")
        parser.add_argument(
            "--economy",
            action="store_true",
            help="Import binary Yes/No markets from Polymarket Economy category",
        )

    def handle(self, *args, **options):
        if options["economy"]:
            from integrations.services import sync_economy_binary_markets

            result = sync_economy_binary_markets(limit=options["limit"])
        else:
            result = import_markets_from_polymarket(
                limit=options["limit"],
                offset=options["offset"],
                active=not options["all"],
            )
        created = sum(1 for i in result["imported"] if i["created"])
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
