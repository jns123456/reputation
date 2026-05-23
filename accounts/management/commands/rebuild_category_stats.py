from django.core.management.base import BaseCommand

from accounts.category_stats_services import rebuild_all_category_stats


class Command(BaseCommand):
    help = "Rebuild per-category reputation and popularity stats from event records."

    def handle(self, *args, **options):
        rebuild_all_category_stats()
        self.stdout.write(self.style.SUCCESS("Category stats rebuilt successfully."))
