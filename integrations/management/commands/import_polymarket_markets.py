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
        parser.add_argument(
            "--crypto",
            action="store_true",
            help="Import binary Yes/No markets from Polymarket Crypto category",
        )
        parser.add_argument(
            "--world-cup",
            action="store_true",
            help="Import FIFA World Cup match markets as 3-outcome forecasts (win/draw/loss)",
        )
        parser.add_argument(
            "--f1",
            action="store_true",
            help="Import Formula 1 props and futures from Polymarket",
        )
        parser.add_argument(
            "--tag",
            type=str,
            default="",
            help="Import binary Yes/No markets for a Polymarket tag slug (e.g. sports, politics)",
        )
        parser.add_argument(
            "--category-name",
            type=str,
            default="",
            help="Default category label when using --tag",
        )

    def handle(self, *args, **options):
        if options["economy"]:
            from integrations.services import sync_economy_binary_markets

            result = sync_economy_binary_markets(limit=options["limit"])
        elif options["crypto"]:
            from integrations.services import sync_crypto_binary_markets

            result = sync_crypto_binary_markets(limit=options["limit"])
        elif options["world_cup"]:
            from integrations.services import sync_world_cup_match_markets

            result = sync_world_cup_match_markets()
        elif options["f1"]:
            from integrations.services import sync_f1_markets

            result = sync_f1_markets(limit=options["limit"] or None)
        elif options["tag"]:
            from integrations.services import sync_binary_markets_by_tag

            category_name = options["category_name"] or options["tag"].replace("-", " ").title()
            result = sync_binary_markets_by_tag(
                tag_slug=options["tag"],
                default_category=category_name,
                limit=options["limit"],
            )
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
