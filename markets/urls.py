from django.urls import path

from markets import views

app_name = "markets"

urlpatterns = [
    path("", views.market_hub, name="list"),
    path("all/", views.market_list, name="all"),
    path("<slug:slug>/", views.market_detail, name="detail"),
    path("<slug:slug>/live-stream/", views.market_live_stream, name="live_stream"),
]
