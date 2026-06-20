from django.contrib import admin

from messaging.models import Conversation, ConversationParticipant, Message


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    readonly_fields = ("user", "last_read_at")


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("sender", "body", "created_at")
    ordering = ("-created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user_one", "user_two", "updated_at", "created_at")
    search_fields = ("user_one__username", "user_two__username")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ConversationParticipantInline, MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at")
    search_fields = ("body", "sender__username")
    readonly_fields = ("created_at",)
