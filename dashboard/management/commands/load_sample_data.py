from django.core.management.base import BaseCommand
from django.utils import timezone

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
                "email_verified_at": timezone.now(),
                "onboarding_completed": True,
            },
        )
        if not admin.has_usable_password():
            admin.set_password("admin123")
            admin.save()
        elif not admin.email_verified_at:
            admin.email_verified_at = timezone.now()
            admin.onboarding_completed = True
            admin.save(update_fields=["email_verified_at", "onboarding_completed"])

        demo, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@example.com",
                "display_name": "Demo User",
                "email_verified_at": timezone.now(),
                "onboarding_completed": True,
            },
        )
        if created:
            demo.set_password("demo123")
            demo.save()
        elif not demo.email_verified_at:
            demo.email_verified_at = timezone.now()
            demo.onboarding_completed = True
            demo.save(update_fields=["email_verified_at", "onboarding_completed"])

        self.stdout.write(
            self.style.SUCCESS(
                "Sample users loaded (admin/admin123, demo/demo123). "
                "Run sync_markets --top-volume to import Polymarket markets."
            )
        )
