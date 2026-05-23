from django.urls import path

from challenges import views

app_name = "challenges"

urlpatterns = [
    path("", views.challenge_list, name="list"),
    path("new/", views.challenge_create, name="create"),
    path("markets/search/", views.challenge_market_search, name="market_search"),
    path("<int:pk>/", views.challenge_detail, name="detail"),
    path("<int:pk>/accept/", views.challenge_accept, name="accept"),
    path("<int:pk>/decline/", views.challenge_decline, name="decline"),
    path("<int:pk>/cancel/", views.challenge_cancel, name="cancel"),
]
