from django.urls import path

from dashboard import admin_panel_views, views

app_name = "dashboard"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("panel/", admin_panel_views.admin_panel, name="admin_panel"),
    path(
        "panel/contest-payouts/<int:payout_id>/",
        admin_panel_views.resolve_contest_payout,
        name="resolve_contest_payout",
    ),
    path(
        "panel/verifications/<int:user_id>/",
        admin_panel_views.resolve_identity_verification,
        name="resolve_identity_verification",
    ),
    path(
        "panel/contest-payouts/<int:payout_id>/",
        admin_panel_views.resolve_contest_payout,
        name="resolve_contest_payout",
    ),
    path("panel/moderation/", admin_panel_views.moderation_queue, name="moderation_queue"),
    path(
        "panel/moderation/action/",
        admin_panel_views.moderation_action,
        name="moderation_action",
    ),
    path("explore/", views.explore, name="explore"),
    path("about/", views.about, name="about"),
    path("legal/", views.legal, name="legal"),
    path("terms/", views.terms, name="terms"),
    path("faq/", views.faq, name="faq"),
    path("browse/<slug:slug>/", views.category_browse, name="category_browse"),
    path("world-cup/games/", views.world_cup_games, name="world_cup_games"),
    path("forecasts/", views.forecasts, name="forecasts"),
    path("forecasts/feed/", views.forecasts_feed, name="forecasts_feed"),
    path("dashboard/", views.home, name="home"),
    path("leaderboard/reputation/", views.reputation_leaderboard, name="reputation_leaderboard"),
    path("leaderboard/agents/", views.agent_arena, name="agent_arena"),
    path("leaderboard/weekly-contest/", views.weekly_contest, name="weekly_contest"),
    path(
        "leaderboard/weekly-contest/dismiss-announcement/",
        views.weekly_contest_dismiss_announcement,
        name="weekly_contest_dismiss_announcement",
    ),
    path("leaderboard/popularity/", views.popularity_leaderboard, name="popularity_leaderboard"),
    path(
        "leaderboard/reputation/category/<slug:slug>/",
        views.reputation_leaderboard_category,
        name="reputation_leaderboard_category",
    ),
    path(
        "leaderboard/popularity/category/<slug:slug>/",
        views.popularity_leaderboard_category,
        name="popularity_leaderboard_category",
    ),
]
