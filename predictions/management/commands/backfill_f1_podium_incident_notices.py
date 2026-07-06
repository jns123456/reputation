from django.core.management.base import BaseCommand

from predictions.incident_notice_services import backfill_f1_podium_incident_notices


class Command(BaseCommand):
    help = (
        "Queue one-time login notices for users affected by the F1 British GP "
        "podium mis-scoring incident."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List affected users without queueing notices.",
        )

    def handle(self, *args, **options):
        result = backfill_f1_podium_incident_notices(dry_run=options["dry_run"])
        if options["dry_run"]:
            self.stdout.write(f"Would queue notices for {len(result)} user(s):")
            for row in result:
                self.stdout.write(
                    f"  user={row['username']} prediction={row['prediction_id']} "
                    f"is_correct_now={row['is_correct_now']}"
                )
            return

        self.stdout.write(self.style.SUCCESS(f"Queued notices for {len(result)} user(s)."))
