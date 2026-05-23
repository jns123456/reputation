from django.contrib import admin

from predictions.models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "market",
        "predicted_outcome",
        "confidence",
        "status",
        "is_correct",
        "created_at",
    )
    list_filter = ("status", "is_correct")
    search_fields = ("user__username", "market__title", "predicted_outcome")
    readonly_fields = ("created_at", "updated_at", "resolved_at", "probability_at_prediction_time")
