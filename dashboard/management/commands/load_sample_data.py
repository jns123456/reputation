from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Load sample markets and users for local development."

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "is_staff": True,
                "is_superuser": True,
                "display_name": "Admin",
            },
        )
        if not admin.has_usable_password():
            admin.set_password("admin123")
            admin.save()

        demo, created = User.objects.get_or_create(
            username="demo",
            defaults={"email": "demo@example.com", "display_name": "Demo User"},
        )
        if created:
            demo.set_password("demo123")
            demo.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Sample users loaded (admin/admin123, demo/demo123). "
                "Run sync_markets --top-volume to import Polymarket markets."
            )
        )
