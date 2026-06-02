from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mcp.models import McpToolCallLog


class Command(BaseCommand):
    help = "Delete MCP audit logs older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Keep logs newer than this many days. Defaults to 90.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be deleted without deleting them.",
        )

    def handle(self, *args, **options):
        days = max(1, options["days"])
        cutoff = timezone.now() - timedelta(days=days)
        queryset = McpToolCallLog.objects.filter(created_at__lt=cutoff)
        count = queryset.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Would delete {count} MCP log rows older than {days} days."
                )
            )
            return

        deleted, _ = queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} MCP log rows older than {days} days."
            )
        )
