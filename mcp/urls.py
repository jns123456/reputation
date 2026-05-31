from django.urls import path

from mcp import views, views_dashboard

app_name = "mcp"

urlpatterns = [
    path("", views.mcp_endpoint, name="endpoint"),
    path("tokens/", views_dashboard.developer_settings, name="developer_settings"),
    path("tokens/<int:token_id>/revoke/", views_dashboard.revoke_token, name="revoke_token"),
    path("tokens/<int:token_id>/rotate/", views_dashboard.rotate_token_view, name="rotate_token"),
]
