from django.urls import path

from pulse import views

app_name = "forum"

urlpatterns = [
    path("", views.pulse, name="feed"),
    path("feed/", views.pulse_feed, name="feed_partial"),
    path("create/", views.create_post_view, name="create"),
    path("<int:post_id>/", views.post_detail, name="detail"),
    path("<int:post_id>/comment/", views.create_comment_view, name="comment"),
    path("<int:post_id>/repost/", views.repost_toggle, name="repost"),
]
