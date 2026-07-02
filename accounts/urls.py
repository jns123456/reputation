from django.urls import path

from accounts import push_views, views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("verify-email/pending/", views.verify_email_pending, name="verify_email_pending"),
    path("verify-email/resend/", views.verify_email_resend, name="verify_email_resend"),
    path("verify-email/<str:token>/", views.verify_email_confirm, name="verify_email_confirm"),
    path("setup/", views.profile_setup, name="profile_setup"),
    path("welcome/", views.onboarding, name="onboarding"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path(
        "password-reset/",
        views.CustomPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/sent/",
        views.CustomPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        views.CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/done/",
        views.CustomPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("auth0/login/", views.auth0_login, name="auth0_login"),
    path("auth0/callback/", views.auth0_callback, name="auth0_callback"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("delete/", views.account_delete, name="account_delete"),
    path("settings/alerts/", views.alert_settings, name="alert_settings"),
    path("notifications/", views.notifications_list, name="notifications"),
    path(
        "notifications/dropdown/",
        views.notifications_dropdown,
        name="notifications_dropdown",
    ),
    path(
        "notifications/<int:notification_id>/open/",
        views.notification_open,
        name="notification_open",
    ),
    path(
        "notifications/<int:notification_id>/read/",
        views.notification_mark_read,
        name="notification_mark_read",
    ),
    path("push/vapid-key/", push_views.vapid_public_key, name="push_vapid_key"),
    path("push/subscribe/", push_views.push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", push_views.push_unsubscribe, name="push_unsubscribe"),
    path("bookmarks/toggle/", views.bookmark_toggle, name="bookmark_toggle"),
    path("bookmarks/", views.bookmarks_list, name="bookmarks"),
    path("follow/toggle/", views.follow_toggle, name="follow_toggle"),
    path("follow/topic/", views.topic_follow_toggle, name="topic_follow_toggle"),
    path(
        "watch/markets/<slug:slug>/",
        views.market_watch_toggle,
        name="market_watch_toggle",
    ),
    path("creator/subscribe/", views.creator_subscribe, name="creator_subscribe"),
    path("creator/unsubscribe/", views.creator_unsubscribe, name="creator_unsubscribe"),
    path("users/search/partial/", views.user_search_partial, name="user_search_partial"),
    path(
        "users/mention-suggestions/",
        views.mention_suggestions_partial,
        name="mention_suggestions_partial",
    ),
    path("users/search/", views.user_search, name="user_search"),
    path("users/list/", views.user_list, name="user_list"),
    path("users/<str:username>/followers/", views.profile_followers, name="profile_followers"),
    path("users/<str:username>/following/", views.profile_following, name="profile_following"),
    path("users/<str:username>/monetize/setup/", views.creator_setup, name="creator_setup"),
    path(
        "users/<str:username>/monetize/subscribers/",
        views.creator_subscribers,
        name="creator_subscribers",
    ),
    path("users/<str:username>/monetize/", views.profile_monetize, name="profile_monetize"),
    path(
        "users/<str:username>/contest-earnings/",
        views.profile_contest_earnings,
        name="profile_contest_earnings",
    ),
    path("users/<str:username>/og.png", views.profile_og_image, name="profile_og"),
    path("users/<str:username>/", views.profile_detail, name="profile"),
]
