from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("browse/<slug:slug>/", views.category_browse, name="category_browse"),
    path("dashboard/", views.home, name="home"),
    path("leaderboard/reputation/", views.reputation_leaderboard, name="reputation_leaderboard"),
    path("leaderboard/popularity/", views.popularity_leaderboard, name="popularity_leaderboard"),
]
