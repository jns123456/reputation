from django.urls import path

from integrations import views

app_name = "integrations"

urlpatterns = [
    path("", views.proof_index, name="proof_index"),
    path("batches/<str:merkle_root>/", views.batch_detail, name="batch_detail"),
    path("attestations/<str:uid>/", views.attestation_detail, name="attestation_detail"),
]
