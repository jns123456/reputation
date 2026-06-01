from django.urls import path

from challenges import views

app_name = "challenges"

urlpatterns = [
    path("", views.challenge_list, name="list"),
    path("how-it-works/", views.challenge_how_it_works, name="how_it_works"),
    path("new/", views.challenge_create, name="create"),
    path("groups/", views.challenge_group_list, name="group_list"),
    path("groups/new/", views.challenge_group_create, name="group_create"),
    path("groups/<int:pk>/edit/", views.challenge_group_edit, name="group_edit"),
    path("groups/<int:pk>/delete/", views.challenge_group_delete, name="group_delete"),
    path("markets/browse/", views.challenge_market_browse, name="market_browse"),
    path("markets/search/", views.challenge_market_search, name="market_search"),
    path("<int:pk>/", views.challenge_detail, name="detail"),
    path("<int:pk>/accept/", views.challenge_accept, name="accept"),
    path("<int:pk>/decline/", views.challenge_decline, name="decline"),
    path("<int:pk>/cancel/", views.challenge_cancel, name="cancel"),
]
