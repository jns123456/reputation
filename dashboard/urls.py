from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("about/", views.about, name="about"),
    path("faq/", views.faq, name="faq"),
    path("browse/<slug:slug>/", views.category_browse, name="category_browse"),
    path("forum/", views.forum, name="forum"),
    path("forum/feed/", views.forum_feed, name="forum_feed"),
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
