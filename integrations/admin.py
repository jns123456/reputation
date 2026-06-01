from django.contrib import admin

from integrations.models import AttestationBatch, AttestationSchema, OffchainAttestation


@admin.register(AttestationSchema)
class AttestationSchemaAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "version", "schema_uid", "is_active", "updated_at")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "schema_uid", "schema")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OffchainAttestation)
class OffchainAttestationAdmin(admin.ModelAdmin):
    list_display = ("short_uid", "schema", "status", "signer", "prediction", "user", "created_at")
    list_filter = ("status", "schema__kind", "signature_algorithm")
    search_fields = ("uid", "signer", "payload_hash", "prediction__market__title", "user__username")
    readonly_fields = (
        "uid",
        "payload_hash",
        "signature",
        "raw_attestation",
        "verified_at",
        "created_at",
        "updated_at",
    )


@admin.register(AttestationBatch)
class AttestationBatchAdmin(admin.ModelAdmin):
    list_display = (
        "short_root",
        "batch_date",
        "record_count",
        "status",
        "chain_id",
        "transaction_hash",
        "created_at",
    )
    list_filter = ("status", "chain_id")
    search_fields = ("merkle_root", "transaction_hash", "signer")
    readonly_fields = ("merkle_root", "created_at", "payload_hash", "signature")
    date_hierarchy = "batch_date"
