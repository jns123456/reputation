from django.core.management.base import BaseCommand

from accounts.models import User
from markets.models import Market


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

        markets_data = [
            {
                "external_id": "sample-1",
                "title": "Will AI surpass human reasoning by 2030?",
                "slug": "ai-surpass-2030",
                "description": "Debate whether artificial general intelligence will exceed human reasoning capabilities before 2030.",
                "category": "Technology",
                "outcomes": [{"label": "Yes"}, {"label": "No"}],
                "current_probability": {"Yes": 0.35, "No": 0.65},
            },
            {
                "external_id": "sample-2",
                "title": "Will the Fed cut rates in Q3 2026?",
                "slug": "fed-cut-q3-2026",
                "description": "Federal Reserve interest rate decision market.",
                "category": "Economics",
                "outcomes": [{"label": "Yes"}, {"label": "No"}],
                "current_probability": {"Yes": 0.55, "No": 0.45},
            },
            {
                "external_id": "sample-3",
                "title": "Who wins the 2028 US Presidential Election?",
                "slug": "us-election-2028",
                "description": "Multi-outcome political prediction market.",
                "category": "Politics",
                "outcomes": [{"label": "Democrat"}, {"label": "Republican"}, {"label": "Other"}],
                "current_probability": {"Democrat": 0.48, "Republican": 0.47, "Other": 0.05},
            },
        ]

        for data in markets_data:
            Market.objects.update_or_create(
                external_id=data["external_id"],
                defaults={
                    "title": data["title"],
                    "slug": data["slug"],
                    "description": data["description"],
                    "category": data["category"],
                    "status": Market.Status.OPEN,
                    "outcomes": data["outcomes"],
                    "current_probability": data["current_probability"],
                    "source": Market.Source.MANUAL,
                },
            )

        self.stdout.write(self.style.SUCCESS("Sample data loaded (admin/admin123, demo/demo123)"))
