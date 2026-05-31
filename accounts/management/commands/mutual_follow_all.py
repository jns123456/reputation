from django.core.management.base import BaseCommand

from accounts.follow_services import ensure_mutual_follows_among_active_users


class Command(BaseCommand):
    help = (
        "Ensure every active user follows every other active user (mutual follows). "
        "Idempotent and safe to re-run; skips existing edges and does not send notifications."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many follow edges would be created without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        result = ensure_mutual_follows_among_active_users(dry_run=dry_run)

        if result["users"] < 2:
            self.stdout.write(
                self.style.WARNING(
                    f"Only {result['users']} active user(s); nothing to do."
                )
            )
            return

        prefix = "Would create" if dry_run else "Created"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix} {result['created']} follow edge(s) among "
                f"{result['users']} active users "
                f"({result['existing']} already existed; "
                f"{result['expected']} total directed edges expected)."
            )
        )
