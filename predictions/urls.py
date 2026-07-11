from django.urls import path

from predictions import views

app_name = "predictions"

urlpatterns = [
    path("open/", views.open_predictions, name="open"),
    path("markets/<slug:slug>/create/", views.create_prediction_view, name="create"),
    path(
        "markets/<slug:slug>/exit/<int:prediction_id>/",
        views.exit_prediction_view,
        name="exit",
    ),
    path(
        "<int:prediction_id>/debrief/",
        views.create_debrief_view,
        name="create_debrief",
    ),
    path("users/<str:username>/history/", views.prediction_history, name="history"),
]
