"""Finalize a quarterly reputation season and mint permanent awards."""

from django.core.management.base import BaseCommand

from reputation.season_services import finalize_season, previous_season_code


class Command(BaseCommand):
    help = "Create permanent SeasonAward badges for a finished season (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            default=None,
            help="Season code like 2026-Q1 (default: most recently ended season).",
        )

    def handle(self, *args, **options):
        season = options["season"] or previous_season_code()
        created = finalize_season(season)
        self.stdout.write(self.style.SUCCESS(f"Season {season}: {created} awards created."))
