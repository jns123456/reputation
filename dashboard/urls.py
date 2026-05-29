from django.urls import path
from django.views.generic import RedirectView

from dashboard import admin_panel_views, views

app_name = "dashboard"

urlpatterns = [
    path("", views.about, name="landing"),
    path("panel/", admin_panel_views.admin_panel, name="admin_panel"),
    path("explore/", views.explore, name="explore"),
    path(
        "about/",
        RedirectView.as_view(pattern_name="dashboard:landing", permanent=False),
        name="about",
    ),
    path("legal/", views.legal, name="legal"),
    path("terms/", views.terms, name="terms"),
    path("faq/", views.faq, name="faq"),
    path("browse/<slug:slug>/", views.category_browse, name="category_browse"),
    path("world-cup/games/", views.world_cup_games, name="world_cup_games"),
    path("forecasts/", views.forecasts, name="forecasts"),
    path("forecasts/feed/", views.forecasts_feed, name="forecasts_feed"),
    path("dashboard/", views.home, name="home"),
    path("leaderboard/reputation/", views.reputation_leaderboard, name="reputation_leaderboard"),
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
