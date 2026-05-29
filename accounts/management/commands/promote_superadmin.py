from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

DEFAULT_SUPERADMIN_EMAIL = "juaninappa@gmail.com"


class Command(BaseCommand):
    help = (
        "Promote a user to platform super admin (is_staff + is_superuser). "
        "Defaults to the platform owner account. Idempotent and safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "email",
            nargs="?",
            default=DEFAULT_SUPERADMIN_EMAIL,
            help=f"Email of the user to promote (default: {DEFAULT_SUPERADMIN_EMAIL}).",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        User = get_user_model()

        users = list(User.objects.filter(email__iexact=email))
        if not users:
            raise CommandError(
                f"No user found with email '{email}'. The user must sign up first."
            )
        if len(users) > 1:
            raise CommandError(
                f"Multiple users share email '{email}'. Resolve the duplicate before promoting."
            )

        user = users[0]
        already = user.is_staff and user.is_superuser
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])

        if already:
            self.stdout.write(
                self.style.WARNING(f"'{email}' was already a super admin. No change needed.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"'{email}' (@{user.username}) is now a super admin.")
            )
