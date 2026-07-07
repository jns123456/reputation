"""Strip bulky Polymarket JSON from inactive markets to reclaim DB space."""

from django.core.management.base import BaseCommand, CommandError

from markets.models import Market
from markets.prune_services import (
    DEFAULT_PRUNE_STATUSES,
    format_bytes,
    merge_prune_stats,
    parse_statuses,
    prune_market_raw_batch,
    prune_market_raw_queryset,
)


class Command(BaseCommand):
    help = (
        "Compact polymarket_raw / polymarket_event_raw on resolved or closed markets. "
        "Denormalized columns and user predictions are untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--status",
            default=",".join(DEFAULT_PRUNE_STATUSES),
            help="Comma-separated market statuses to prune (default: resolved,closed).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Markets processed per batch (default: 500).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum markets to examine (0 = no limit).",
        )
        parser.add_argument(
            "--min-saved-bytes",
            type=int,
            default=512,
            help="Skip rows where compaction saves less than this many bytes.",
        )
        parser.add_argument(
            "--allow-open",
            action="store_true",
            help=(
                "Allow pruning open markets. Not recommended — sync and forecast UI "
                "rely on full payloads until re-fetched from Polymarket."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would change without writing to the database.",
        )

    def handle(self, *args, **options):
        try:
            statuses = parse_statuses(options["status"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if Market.Status.OPEN in statuses and not options["allow_open"]:
            raise CommandError(
                "Refusing to prune open markets without --allow-open. "
                "Default scope is resolved,closed only."
            )

        batch_size = max(1, options["batch_size"])
        limit = max(0, options["limit"])
        min_saved_bytes = max(0, options["min_saved_bytes"])
        dry_run = options["dry_run"]

        queryset = prune_market_raw_queryset(statuses=statuses)
        pending = queryset.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run — {pending} candidate markets with status "
                    f"{', '.join(statuses)}."
                )
            )
        else:
            self.stdout.write(
                f"Pruning up to {pending} markets (status: {', '.join(statuses)})."
            )

        totals = {
            "examined": 0,
            "updated": 0,
            "skipped": 0,
            "bytes_before": 0,
            "bytes_after": 0,
        }
        last_pk = 0

        while True:
            if limit and totals["examined"] >= limit:
                break

            remaining = batch_size
            if limit:
                remaining = min(remaining, limit - totals["examined"])
            if remaining <= 0:
                break

            batch = list(
                queryset.filter(pk__gt=last_pk).select_related(None)[:remaining]
            )
            if not batch:
                break

            last_pk = batch[-1].pk
            batch_stats = prune_market_raw_batch(
                batch,
                dry_run=dry_run,
                min_saved_bytes=min_saved_bytes,
            )
            merge_prune_stats(totals, batch_stats)

            if totals["updated"] and totals["updated"] % 5000 == 0:
                saved = totals["bytes_before"] - totals["bytes_after"]
                self.stdout.write(
                    f"  … {totals['updated']} compacted so far "
                    f"({format_bytes(saved)} JSON saved)"
                )

        saved = totals["bytes_before"] - totals["bytes_after"]
        action = "Would compact" if dry_run else "Compacted"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} {totals['updated']} markets "
                f"(examined {totals['examined']}, skipped {totals['skipped']}). "
                f"Estimated JSON reduction: {format_bytes(saved)}."
            )
        )

        if not dry_run and totals["updated"]:
            self.stdout.write(
                self.style.WARNING(
                    "Run VACUUM on markets_market to reclaim disk on Postgres "
                    "(e.g. heroku pg:psql -c \"VACUUM FULL markets_market;\"). "
                    "Capture a backup first: heroku pg:backups:capture."
                )
            )
