from django.urls import path

from predictions import views

app_name = "predictions"

urlpatterns = [
    path("markets/<slug:slug>/create/", views.create_prediction_view, name="create"),
    path("users/<str:username>/history/", views.prediction_history, name="history"),
]
