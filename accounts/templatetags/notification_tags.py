from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from accounts.models import Notification

register = template.Library()

LINK_CLASS = "text-brand-600 hover:underline dark:text-brand-400"
ACTOR_LINK_CLASS = "font-semibold text-brand-600 hover:underline dark:text-brand-400"


def _actor_link(notification):
    name = notification.actor.public_name
    from django.urls import reverse

    profile_url = reverse("accounts:profile", kwargs={"username": notification.actor.username})
    return format_html(
        '<a href="{}" class="{}">{}</a>',
        profile_url,
        ACTOR_LINK_CLASS,
        name,
    )


@register.simple_tag
def notification_icon_bg(notification):
    icons = {
        Notification.NotificationType.FOLLOWED_USER_PREDICTION: "bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-300",
        Notification.NotificationType.NEW_FOLLOWER: "bg-violet-100 text-violet-600 dark:bg-violet-900/40 dark:text-violet-300",
        Notification.NotificationType.UPVOTE_RECEIVED: "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-300",
        Notification.NotificationType.DOWNVOTE_RECEIVED: "bg-rose-100 text-rose-600 dark:bg-rose-900/40 dark:text-rose-300",
        Notification.NotificationType.PREDICTION_RESOLVED: "bg-amber-100 text-amber-600 dark:bg-amber-900/40 dark:text-amber-300",
        Notification.NotificationType.CHALLENGE_INVITATION: "bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-300",
        Notification.NotificationType.CHALLENGE_MARKET_RESOLVED: "bg-sky-100 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300",
        Notification.NotificationType.CHALLENGE_COMPLETED: "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-300",
        Notification.NotificationType.CHALLENGE_ACCEPTED: "bg-violet-100 text-violet-600 dark:bg-violet-900/40 dark:text-violet-300",
    }
    return icons.get(notification.notification_type, "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300")


@register.simple_tag
def notification_icon(notification):
    icons = {
        Notification.NotificationType.FOLLOWED_USER_PREDICTION: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>'
        ),
        Notification.NotificationType.NEW_FOLLOWER: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/></svg>'
        ),
        Notification.NotificationType.UPVOTE_RECEIVED: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"/></svg>'
        ),
        Notification.NotificationType.DOWNVOTE_RECEIVED: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.737 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5"/></svg>'
        ),
        Notification.NotificationType.PREDICTION_RESOLVED: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
        ),
        Notification.NotificationType.CHALLENGE_INVITATION: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>'
        ),
        Notification.NotificationType.CHALLENGE_MARKET_RESOLVED: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
        ),
        Notification.NotificationType.CHALLENGE_COMPLETED: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>'
        ),
        Notification.NotificationType.CHALLENGE_ACCEPTED: (
            '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
        ),
    }
    return mark_safe(icons.get(notification.notification_type, ""))


def _challenge_market_resolved_message(notification):
    from django.urls import reverse

    challenge_url = reverse("challenges:detail", kwargs={"pk": notification.challenge_id})
    challenge_title = notification.challenge.display_title
    market_title = notification.market.display_title if notification.market_id else _("An event")
    outcome = notification.market.resolved_outcome if notification.market_id else ""
    outcome_html = (
        format_html(' {}: <span class="font-semibold">{}</span>.', _("Result"), outcome)
        if outcome
        else ""
    )
    return format_html(
        '{in_text} <a href="{url}" class="{link}">{title}</a>, '
        '<span class="font-semibold">{market}</span> {resolved}{outcome}',
        in_text=_("In"),
        url=challenge_url,
        link=LINK_CLASS,
        title=challenge_title,
        market=market_title,
        resolved=_("was resolved."),
        outcome=mark_safe(outcome_html),
    )


def _challenge_completed_message(notification):
    from django.urls import reverse

    challenge_url = reverse("challenges:detail", kwargs={"pk": notification.challenge_id})
    challenge_title = notification.challenge.display_title
    winner = notification.challenge.winner
    if winner and winner.id == notification.recipient_id:
        return format_html(
            '{} <a href="{}" class="{}">{}</a>!',
            _("You won"),
            challenge_url,
            LINK_CLASS,
            challenge_title,
        )
    if winner:
        return format_html(
            '<a href="{}" class="{}">{}</a> {} '
            '<span class="font-semibold">{}</span>.',
            challenge_url,
            LINK_CLASS,
            challenge_title,
            _("is complete. Winner:"),
            winner.public_name,
        )
    return format_html(
        '<a href="{}" class="{}">{}</a> {}.',
        challenge_url,
        LINK_CLASS,
        challenge_title,
        _("ended in a tie"),
    )


@register.simple_tag
def notification_message(notification, compact=False):
    from django.urls import reverse

    actor = _actor_link(notification)
    t = notification.notification_type

    if t == Notification.NotificationType.NEW_FOLLOWER:
        return format_html("{} {}", actor, _("started following you"))

    if t == Notification.NotificationType.FOLLOWED_USER_PREDICTION and notification.prediction_id:
        market_url = reverse(
            "markets:detail",
            kwargs={"slug": notification.prediction.market.slug},
        )
        market_title = notification.prediction.market.display_title
        return format_html(
            "{} {} <a href=\"{}\" class=\"{}\">{}</a>",
            actor,
            _("published a forecast on"),
            market_url,
            LINK_CLASS,
            market_title,
        )

    if t == Notification.NotificationType.UPVOTE_RECEIVED:
        content = _vote_content_label(notification)
        return format_html("{} {} {}", actor, _("liked your"), content)

    if t == Notification.NotificationType.DOWNVOTE_RECEIVED:
        content = _vote_content_label(notification)
        return format_html("{} {} {}", actor, _("disliked your"), content)

    if t == Notification.NotificationType.PREDICTION_RESOLVED and notification.prediction_id:
        market_url = reverse(
            "markets:detail",
            kwargs={"slug": notification.prediction.market.slug},
        )
        market_title = notification.prediction.market.display_title
        delta = notification.reputation_event.points_delta if notification.reputation_event_id else 0
        outcome_label = _("correct") if notification.prediction.is_correct else _("incorrect")
        delta_label = f"+{delta}" if delta >= 0 else str(delta)
        return format_html(
            '{market} <a href="{url}" class="{link}">{title}</a> '
            "{resolved} {outcome} — "
            '<span class="font-semibold">{delta}</span> {points}.',
            market=_("Market"),
            url=market_url,
            link=LINK_CLASS,
            title=market_title,
            resolved=_("was resolved. Your forecast was"),
            outcome=outcome_label,
            delta=delta_label,
            points=_("reputation points"),
        )

    if t == Notification.NotificationType.CHALLENGE_INVITATION and notification.challenge_id:
        challenge_url = reverse("challenges:detail", kwargs={"pk": notification.challenge_id})
        challenge_title = notification.challenge.display_title
        return format_html(
            '{} {} <a href="{}" class="{}">{}</a>',
            actor,
            _("challenged you to"),
            challenge_url,
            LINK_CLASS,
            challenge_title,
        )

    if t == Notification.NotificationType.CHALLENGE_ACCEPTED and notification.challenge_id:
        challenge_url = reverse("challenges:detail", kwargs={"pk": notification.challenge_id})
        challenge_title = notification.challenge.display_title
        return format_html(
            '{} {} <a href="{}" class="{}">{}</a>',
            actor,
            _("accepted your challenge"),
            challenge_url,
            LINK_CLASS,
            challenge_title,
        )

    if t == Notification.NotificationType.CHALLENGE_MARKET_RESOLVED and notification.challenge_id:
        return _challenge_market_resolved_message(notification)

    if t == Notification.NotificationType.CHALLENGE_COMPLETED and notification.challenge_id:
        return _challenge_completed_message(notification)

    return format_html("{} {}", actor, _("sent you a notification"))


def _vote_content_label(notification):
    if notification.comment_id:
        return _("comment")
    if notification.prediction_id:
        return _("forecast")
    return _("content")
