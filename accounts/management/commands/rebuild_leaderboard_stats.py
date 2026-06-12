from django.core.management.base import BaseCommand

from accounts.category_stats_services import rebuild_all_category_stats
from accounts.profile_stats_services import rebuild_profile_reputation_counters


class Command(BaseCommand):
    help = (
        "Rebuild leaderboard counters from reputation events, "
        "including retroactive early exits (scored/correct/incorrect + category stats)."
    )

    def handle(self, *args, **options):
        profile_updates = rebuild_profile_reputation_counters()
        rebuild_all_category_stats()
        self.stdout.write(
            self.style.SUCCESS(
                f"Leaderboard stats rebuilt ({profile_updates} profile(s) updated)."
            )
        )
