from django.urls import path

from api import views

app_name = "api"

urlpatterns = [
    path("docs/", views.api_docs, name="docs"),
]
