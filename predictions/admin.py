from django.contrib import admin

from predictions.models import ForecastDebrief, Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "market",
        "predicted_outcome",
        "predicted_direction",
        "confidence",
        "status",
        "is_correct",
        "created_at",
    )
    list_filter = ("status", "is_correct")
    search_fields = ("user__username", "market__title", "predicted_outcome", "predicted_direction")
    readonly_fields = ("created_at", "updated_at", "resolved_at", "probability_at_prediction_time")


@admin.register(ForecastDebrief)
class ForecastDebriefAdmin(admin.ModelAdmin):
    list_display = ("user", "prediction", "popularity_score", "created_at")
    search_fields = ("user__username", "body", "prediction__market__title")
    readonly_fields = ("created_at", "updated_at", "prediction", "user")
    raw_id_fields = ("prediction", "user")
