from django.urls import path

from messaging import views

app_name = "messages"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("with/<str:username>/", views.start_with_user, name="start"),
    path("<int:conversation_id>/", views.thread, name="thread"),
    path("<int:conversation_id>/send/", views.send_message_view, name="send"),
    path("<int:conversation_id>/poll/", views.poll_thread_view, name="poll"),
]
