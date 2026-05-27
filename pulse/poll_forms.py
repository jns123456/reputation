"""Poll parsing and validation for forum posts."""

from django import forms
from django.utils.translation import gettext_lazy as _

POLL_DURATION_CHOICES = (1, 3, 7)
MAX_POLL_OPTIONS = 4
MIN_POLL_OPTIONS = 2
MAX_POLL_OPTION_LENGTH = 50


def parse_poll_options_from_post(data):
    """Return stripped poll option texts from numbered POST fields, or None if no poll."""
    if data.get("enable_poll") != "1":
        return None

    options = []
    for index in range(MAX_POLL_OPTIONS):
        raw = (data.get(f"poll_option_{index}") or "").strip()
        if raw:
            options.append(raw)

    duration_raw = data.get("poll_days", "1")
    try:
        duration_days = int(duration_raw)
    except (TypeError, ValueError):
        duration_days = 1

    if duration_days not in POLL_DURATION_CHOICES:
        duration_days = 1

    return {
        "options": options,
        "duration_days": duration_days,
    }


class PollValidationError(forms.ValidationError):
    pass


def validate_poll_payload(*, poll_payload, body="", has_image=False):
    if poll_payload is None:
        return

    if has_image:
        raise PollValidationError(_("Polls can't include images."))

    options = poll_payload["options"]
    if len(options) < MIN_POLL_OPTIONS:
        raise PollValidationError(_("Add at least two poll choices."))

    if len(options) > MAX_POLL_OPTIONS:
        raise PollValidationError(_("Polls can have at most four choices."))

    for option in options:
        if len(option) > MAX_POLL_OPTION_LENGTH:
            raise PollValidationError(
                _("Each poll choice must be %(max)s characters or fewer.")
                % {"max": MAX_POLL_OPTION_LENGTH}
            )

    if not body and not options:
        raise PollValidationError(_("Add text or poll choices to your post."))
