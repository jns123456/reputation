from django.urls import path

from integrations import views

app_name = "integrations"

urlpatterns = [
    path("attestations/<str:uid>/", views.attestation_detail, name="attestation_detail"),
]
