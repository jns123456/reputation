from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from accounts import abuse_services
from accounts.models import User
from accounts.write_guard import ContentRejected, write_guard_user_message
from messaging.forms import MessageForm
from messaging.selectors import (
    conversation_unread_count,
    get_conversation_messages,
    get_inbox_conversations,
    get_user_conversation,
)
from messaging.services import mark_conversation_read, send_message


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _htmx_compose_error(request, message, *, status=400):
    response = HttpResponse(message, status=status)
    if _is_htmx(request):
        response["HX-Retarget"] = "#dm-compose-error"
        response["HX-Reswap"] = "innerHTML"
    return response


def _conversation_context(*, request, conversation):
    other = conversation.other_user(request.user)
    mark_conversation_read(user=request.user, conversation=conversation)
    message_list = get_conversation_messages(conversation=conversation)
    return {
        "conversation": conversation,
        "other_user": other,
        "messages": message_list,
        "message_form": MessageForm(),
        "active_conversation_id": conversation.id,
    }


@login_required
@require_GET
def inbox(request):
    return _render_messages_page(request=request, conversation_id=None)


@login_required
@require_GET
def thread(request, conversation_id):
    return _render_messages_page(request=request, conversation_id=conversation_id)


def _render_messages_page(*, request, conversation_id):
    conversations = get_inbox_conversations(user=request.user)
    inbox_rows = []
    for conversation in conversations:
        other = conversation.other_user(request.user)
        latest = conversation.latest_messages[0] if conversation.latest_messages else None
        unread = conversation_unread_count(conversation=conversation, user=request.user)
        inbox_rows.append(
            {
                "conversation": conversation,
                "other_user": other,
                "latest_message": latest,
                "unread_count": unread,
            }
        )

    thread_context = {}
    if conversation_id:
        conversation = get_user_conversation(user=request.user, conversation_id=conversation_id)
        if conversation is None:
            messages.error(request, _("Conversation not found."))
            return redirect("messages:inbox")
        thread_context = _conversation_context(request=request, conversation=conversation)

    context = {
        "inbox_rows": inbox_rows,
        "has_active_thread": bool(thread_context),
        **thread_context,
    }
    return render(request, "messages/inbox.html", context)


@login_required
@require_GET
def start_with_user(request, username):
    other = get_object_or_404(User.objects.select_related("profile"), username=username)
    if other.id == request.user.id:
        messages.error(request, _("You cannot message yourself."))
        return redirect("messages:inbox")

    from messaging.services import get_or_create_conversation

    conversation = get_or_create_conversation(user_a=request.user, user_b=other)
    return redirect("messages:thread", conversation_id=conversation.id)


@login_required
@require_POST
def send_message_view(request, conversation_id):
    conversation = get_user_conversation(user=request.user, conversation_id=conversation_id)
    if conversation is None:
        if _is_htmx(request):
            return HttpResponseForbidden(_("Conversation not found."))
        messages.error(request, _("Conversation not found."))
        return redirect("messages:inbox")

    form = MessageForm(request.POST, request.FILES)
    if not form.is_valid():
        if _is_htmx(request):
            return _htmx_compose_error(request, form.errors.as_text(), status=400)
        messages.error(request, _("Could not send your message."))
        return redirect("messages:thread", conversation_id=conversation.id)

    recipient = conversation.other_user(request.user)
    try:
        message = send_message(
            sender=request.user,
            recipient=recipient,
            body=form.cleaned_data["body"],
            image=form.cleaned_data.get("image"),
        )
    except abuse_services.RateLimitExceeded as exc:
        msg = write_guard_user_message(exc)
        if _is_htmx(request):
            return _htmx_compose_error(request, msg, status=429)
        messages.error(request, msg)
        return redirect("messages:thread", conversation_id=conversation.id)
    except ContentRejected as exc:
        msg = write_guard_user_message(exc)
        if _is_htmx(request):
            return _htmx_compose_error(request, msg, status=400)
        messages.error(request, msg)
        return redirect("messages:thread", conversation_id=conversation.id)
    except ValueError as exc:
        if _is_htmx(request):
            return _htmx_compose_error(request, str(exc), status=400)
        messages.error(request, str(exc))
        return redirect("messages:thread", conversation_id=conversation.id)

    if _is_htmx(request):
        return render(
            request,
            "messages/partials/message_bubble.html",
            {"message": message, "viewer": request.user},
        )

    return redirect("messages:thread", conversation_id=conversation.id)


@login_required
@require_GET
def poll_thread_view(request, conversation_id):
    conversation = get_user_conversation(user=request.user, conversation_id=conversation_id)
    if conversation is None:
        return HttpResponse(status=404)

    mark_conversation_read(user=request.user, conversation=conversation)
    message_list = get_conversation_messages(conversation=conversation)
    return render(
        request,
        "messages/partials/message_list.html",
        {
            "conversation": conversation,
            "messages": message_list,
            "viewer": request.user,
        },
    )
