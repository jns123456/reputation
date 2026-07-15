"""Delete resolved markets with no user activity to reclaim DB space."""

from django.core.management.base import BaseCommand, CommandError

from markets.cleanup_services import (
    ORDER_FIFO,
    ORDER_PK,
    parse_delete_order,
    run_orphan_resolved_cleanup,
)


class Command(BaseCommand):
    help = (
        "Delete resolved markets that have no predictions, comments, challenges, "
        "watches, or notifications. Oldest first by default (FIFO)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=None,
            help="Only delete orphans whose resolution/close date is at least N days ago.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum markets to delete (0 = no limit besides fraction).",
        )
        parser.add_argument(
            "--min-fraction-of-resolved",
            type=float,
            default=0.0,
            help=(
                "Delete at least this fraction of all resolved markets "
                "(capped by orphan count). Example: 0.5 deletes half of resolved."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Delete batch size (default: 500).",
        )
        parser.add_argument(
            "--order",
            default=ORDER_FIFO,
            choices=[ORDER_FIFO, ORDER_PK],
            help="Deletion order: fifo (oldest first) or pk.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would be deleted without writing.",
        )

    def handle(self, *args, **options):
        try:
            order = parse_delete_order(options["order"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        fraction = options["min_fraction_of_resolved"]
        if fraction < 0 or fraction > 1:
            raise CommandError("--min-fraction-of-resolved must be between 0 and 1.")

        older = options["older_than_days"]
        if older is not None and older < 0:
            raise CommandError("--older-than-days must be >= 0.")

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no rows will be deleted."))

        stats = run_orphan_resolved_cleanup(
            older_than_days=older,
            limit=max(0, options["limit"]),
            min_fraction_of_resolved=fraction,
            batch_size=max(1, options["batch_size"]),
            order=order,
            dry_run=dry_run,
        )

        action = "Would delete" if dry_run else "Deleted"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} {stats['deleted']} orphan resolved markets "
                f"(target {stats['target']}, orphans {stats['orphan_total']}, "
                f"resolved total {stats['resolved_total']})."
            )
        )

        if not dry_run and stats["deleted"]:
            self.stdout.write(
                self.style.WARNING(
                    "Reclaim disk with: heroku pg:backups:capture && "
                    'heroku pg:psql -c "VACUUM FULL markets_market;"'
                )
            )
