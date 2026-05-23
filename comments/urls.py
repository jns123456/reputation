from django.urls import path

from comments import views

app_name = "comments"

urlpatterns = [
    path("markets/<slug:slug>/create/", views.create_comment_view, name="create"),
    path("vote/", views.vote_view, name="vote"),
    path("<int:comment_id>/votes/", views.comment_vote_partial, name="vote_partial"),
]
