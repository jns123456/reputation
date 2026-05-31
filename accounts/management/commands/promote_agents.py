"""Evaluate and apply automatic agent trust promotions (AGENTS.md §15)."""

from django.core.management.base import BaseCommand

from accounts.trust_services import promote_eligible_agents


class Command(BaseCommand):
    help = "Evaluate AI-agent profiles and apply rule-based trust promotions."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        summary = promote_eligible_agents(limit=options.get("limit"))
        self.stdout.write(
            self.style.SUCCESS(
                "Agent trust evaluation: "
                f"evaluated={summary['evaluated']} changed={summary['changed']} "
                f"promotions={summary['promotions']} restrictions={summary['restrictions']}"
            )
        )
