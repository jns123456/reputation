from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("setup/", views.profile_setup, name="profile_setup"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("profile/avatar/", views.avatar_upload, name="avatar_upload"),
    path("settings/alerts/", views.alert_settings, name="alert_settings"),
    path("notifications/", views.notifications_list, name="notifications"),
    path(
        "notifications/dropdown/",
        views.notifications_dropdown,
        name="notifications_dropdown",
    ),
    path(
        "notifications/<int:notification_id>/read/",
        views.notification_mark_read,
        name="notification_mark_read",
    ),
    path(
        "notifications/mark-all-read/",
        views.notifications_mark_all_read,
        name="notifications_mark_all_read",
    ),
    path("bookmarks/toggle/", views.bookmark_toggle, name="bookmark_toggle"),
    path("bookmarks/", views.bookmarks_list, name="bookmarks"),
    path("follow/toggle/", views.follow_toggle, name="follow_toggle"),
    path("users/search/partial/", views.user_search_partial, name="user_search_partial"),
    path("users/search/", views.user_search, name="user_search"),
    path("users/<str:username>/", views.profile_detail, name="profile"),
]
