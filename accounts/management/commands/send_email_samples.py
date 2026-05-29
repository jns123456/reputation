"""Send sample transactional emails (verification + welcome) for manual QA."""

import time
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError

from accounts.email_services import EmailDeliveryError, _send, absolute_url, send_welcome_email


class Command(BaseCommand):
    help = "Send sample verification and welcome emails to a recipient address."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            required=True,
            help="Recipient email address (must be allowed by your Resend setup).",
        )
        parser.add_argument(
            "--name",
            default="Juan",
            help="Display name used in the email body.",
        )
        parser.add_argument(
            "--verification-only",
            action="store_true",
            help="Send only the email verification sample.",
        )
        parser.add_argument(
            "--welcome-only",
            action="store_true",
            help="Send only the welcome sample.",
        )

    def handle(self, *args, **options):
        recipient_email = options["to"].strip().lower()
        display_name = options["name"].strip() or "PredictStamp user"
        sample_user = SimpleNamespace(
            email=recipient_email,
            public_name=display_name,
        )
        send_verification = not options["welcome_only"]
        send_welcome = not options["verification_only"]

        if options["verification_only"] and options["welcome_only"]:
            raise CommandError("Choose at most one of --verification-only or --welcome-only.")

        sent_labels = []

        if send_verification:
            verify_url = absolute_url("/accounts/verify-email/sample-token-demo/")
            verification_sent = _send(
                subject="Confirma tu email en PredictStamp",
                recipient_email=recipient_email,
                template_base="email_verification",
                context={
                    "recipient": sample_user,
                    "verify_url": verify_url,
                    "expires_hours": 48,
                    "subject": "Confirma tu email en PredictStamp",
                },
            )
            if not verification_sent:
                raise CommandError("Verification sample email was not accepted by the provider.")
            sent_labels.append("verificación")
            if send_welcome:
                time.sleep(1.5)

        if send_welcome:
            try:
                welcome_sent = send_welcome_email(user=sample_user)
            except EmailDeliveryError as exc:
                raise CommandError(f"Welcome sample email failed: {exc}") from exc
            if not welcome_sent:
                raise CommandError("Welcome sample email was not accepted by the provider.")
            sent_labels.append("bienvenida")

        self.stdout.write(
            self.style.SUCCESS(
                f"Enviado(s) email(s) de {' + '.join(sent_labels)} a {recipient_email}."
            )
        )
