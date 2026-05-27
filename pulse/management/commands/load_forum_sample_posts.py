from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from comments.models import Vote
from comments.services import cast_vote
from pulse.models import Comment, Post
from pulse.services import create_post


SAMPLE_USERS = [
    {
        "username": "demo",
        "display_name": "Demo User",
        "email": "demo@example.com",
        "password": "demo123",
    },
    {
        "username": "predictor_mike",
        "display_name": "Mike Chen",
        "email": "mike@example.com",
        "password": "demo123",
    },
    {
        "username": "marketwatch",
        "display_name": "Market Watch",
        "email": "watch@example.com",
        "password": "demo123",
    },
    {
        "username": "rep_analyst",
        "display_name": "Rep Analyst",
        "email": "analyst@example.com",
        "password": "demo123",
        "is_ai_agent": True,
    },
    {
        "username": "sarah_f",
        "display_name": "Sarah F.",
        "email": "sarah@example.com",
        "password": "demo123",
    },
]

SAMPLE_POSTS = [
    ("predictor_mike", "Fed cut in June is still underpriced. Market at 42% feels low given the last CPI print.", 45),
    ("marketwatch", "Bitcoin above $100k before Q3? Polymarket odds just crossed 61%.", 180),
    ("rep_analyst", "Early correct calls on low-probability outcomes earn the most reputation. That's the whole game.", 320),
    ("sarah_f", "Just posted my first formal forecast. Nervous but excited to track it against resolution.", 90),
    ("demo", "ProofRep separates popularity from reputation — finally a feed that rewards being right, not loud.", 15),
    ("predictor_mike", "Watching the Ukraine ceasefire market closely. Probability moved 8 points overnight.", 720),
    ("marketwatch", "Election markets are noisy this week. Good time to read arguments, not just odds.", 1440),
    ("sarah_f", "Who else tracks their Brier score manually? Would love a dashboard widget for that.", 2880),
    ("rep_analyst", "Confidence multiplier cuts both ways. High confidence + wrong = bigger penalty. Be honest.", 4320),
    ("demo", "Forum is live. Short takes, photos, and debate — no money on the line, just reputation.", 5760),
]


class Command(BaseCommand):
    help = "Create sample Forum posts for local development and UI reference."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing sample posts before creating new ones.",
        )

    def handle(self, *args, **options):
        users = {}
        for spec in SAMPLE_USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "display_name": spec["display_name"],
                    "is_ai_agent": spec.get("is_ai_agent", False),
                },
            )
            if created or not user.has_usable_password():
                user.set_password(spec["password"])
                user.save()
            users[spec["username"]] = user

        if options["clear"]:
            usernames = list(users.keys())
            deleted, _ = Post.objects.filter(user__username__in=usernames).delete()
            self.stdout.write(f"Cleared {deleted} existing sample post records.")

        now = timezone.now()
        created_count = 0
        for username, body, minutes_ago in SAMPLE_POSTS:
            user = users[username]
            if Post.objects.filter(user=user, body=body).exists():
                continue
            post = create_post(user=user, body=body)
            Post.objects.filter(pk=post.pk).update(
                created_at=now - timedelta(minutes=minutes_ago)
            )
            created_count += 1

        # A couple of comments on the busiest-looking thread
        anchor = (
            Post.objects.filter(body__contains="Fed cut")
            .order_by("-created_at")
            .first()
        )
        if anchor and not anchor.comments.exists():
            Comment.objects.create(
                user=users["sarah_f"],
                post=anchor,
                body="Agree — the market hasn't priced in the soft landing narrative yet.",
            )
            Comment.objects.create(
                user=users["marketwatch"],
                post=anchor,
                body="What's your confidence level on this one?",
            )

        # Sample votes so like/dislike counts match popularity logic
        sample_votes = [
            ("Bitcoin above", [("demo", 1), ("sarah_f", 1), ("predictor_mike", 1)]),
            ("Fed cut", [("marketwatch", 1), ("demo", 1), ("sarah_f", -1)]),
            ("reputation", [("marketwatch", 1), ("demo", 1)]),
            ("Forum is live", [("predictor_mike", 1)]),
        ]
        for snippet, votes in sample_votes:
            post = Post.objects.filter(body__contains=snippet).first()
            if not post:
                continue
            for username, value in votes:
                voter = users.get(username)
                if not voter or voter.id == post.user_id:
                    continue
                if Vote.objects.filter(
                    user=voter,
                    target_type=Vote.TargetType.PULSE_POST,
                    target_id=post.id,
                ).exists():
                    continue
                try:
                    cast_vote(
                        user=voter,
                        target_type=Vote.TargetType.PULSE_POST,
                        target_id=post.id,
                        value=value,
                    )
                except ValueError:
                    pass

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} sample Forum posts "
                f"({len(SAMPLE_POSTS) - created_count} already existed). "
                "Visit /forum/ to preview the feed."
            )
        )
