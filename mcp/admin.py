from django.contrib import admin

from mcp.models import McpToken, McpToolCallLog


@admin.register(McpToken)
class McpTokenAdmin(admin.ModelAdmin):
    list_display = (
        "prefix",
        "user",
        "name",
        "rate_limit_tier",
        "is_active",
        "created_at",
        "last_used_at",
        "revoked_at",
    )
    list_filter = ("is_active", "rate_limit_tier")
    search_fields = ("prefix", "name", "user__username")
    # token_hash is a one-way hash; never editable and never shows the raw secret.
    readonly_fields = ("token_hash", "prefix", "created_at", "last_used_at")
    actions = ["revoke_tokens"]

    @admin.action(description="Revoke selected tokens")
    def revoke_tokens(self, request, queryset):
        for token in queryset:
            token.revoke()


@admin.register(McpToolCallLog)
class McpToolCallLogAdmin(admin.ModelAdmin):
    list_display = (
        "tool_name",
        "status",
        "user",
        "agent_id",
        "risk_score",
        "error_code",
        "created_at",
    )
    list_filter = ("status", "tool_name")
    search_fields = ("tool_name", "request_id", "user__username")
    readonly_fields = (
        "token",
        "user",
        "agent_id",
        "tool_name",
        "input_hash",
        "status",
        "error_code",
        "risk_score",
        "request_id",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
