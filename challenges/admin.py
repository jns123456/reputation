from django.contrib import admin

from challenges.models import Challenge, ChallengeGroup, ChallengeMarket, ChallengeParticipant


class ChallengeMarketInline(admin.TabularInline):
    model = ChallengeMarket
    extra = 0
    raw_id_fields = ["market"]


class ChallengeParticipantInline(admin.TabularInline):
    model = ChallengeParticipant
    extra = 0
    raw_id_fields = ["user"]


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ["id", "display_title", "creator", "status", "winner", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "creator__username"]
    raw_id_fields = ["creator", "winner"]
    inlines = [ChallengeMarketInline, ChallengeParticipantInline]


@admin.register(ChallengeMarket)
class ChallengeMarketAdmin(admin.ModelAdmin):
    list_display = ["challenge", "market", "position"]
    raw_id_fields = ["challenge", "market"]


@admin.register(ChallengeParticipant)
class ChallengeParticipantAdmin(admin.ModelAdmin):
    list_display = ["challenge", "user", "status", "joined_at"]
    list_filter = ["status"]
    raw_id_fields = ["challenge", "user"]


@admin.register(ChallengeGroup)
class ChallengeGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "member_count", "updated_at"]
    search_fields = ["name", "owner__username"]
    raw_id_fields = ["owner"]
    filter_horizontal = ["members"]

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()
