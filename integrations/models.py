from django.conf import settings
from django.db import models


class AttestationSchema(models.Model):
    class Kind(models.TextChoices):
        PREDICTION_CLAIM = "prediction_claim", "Prediction claim"
        PREDICTION_RESOLUTION = "prediction_resolution", "Prediction resolution"
        REPUTATION_EVENT = "reputation_event", "Reputation event"
        PROFILE_SUMMARY = "profile_summary", "Profile summary"
        DAILY_BATCH_ANCHOR = "daily_batch_anchor", "Daily batch anchor"

    kind = models.CharField(max_length=50, choices=Kind.choices)
    name = models.CharField(max_length=120)
    schema_uid = models.CharField(max_length=66, unique=True)
    schema = models.TextField()
    version = models.PositiveSmallIntegerField(default=1)
    chain_id = models.PositiveIntegerField(default=0)
    verifying_contract = models.CharField(max_length=66, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "version"],
                name="unique_attestation_schema_kind_version",
            )
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"


class OffchainAttestation(models.Model):
    class Status(models.TextChoices):
        VERIFIED = "verified", "Verified"
        FAILED = "failed", "Failed"
        REVOKED = "revoked", "Revoked"

    schema = models.ForeignKey(
        AttestationSchema,
        on_delete=models.PROTECT,
        related_name="attestations",
    )
    uid = models.CharField(max_length=66, unique=True)
    signer = models.CharField(max_length=120)
    recipient = models.CharField(max_length=120, blank=True)
    ref_uid = models.CharField(max_length=66, blank=True)
    payload = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=66)
    signature = models.CharField(max_length=128)
    signature_algorithm = models.CharField(
        max_length=40,
        default="proofrep-hmac-sha256",
    )
    raw_attestation = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VERIFIED,
        db_index=True,
    )
    prediction = models.ForeignKey(
        "predictions.Prediction",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attestations",
    )
    reputation_event = models.ForeignKey(
        "reputation.ReputationEvent",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attestations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attestations",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["prediction", "status"]),
            models.Index(fields=["reputation_event", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.schema.kind}: {self.uid}"

    @property
    def short_uid(self):
        return f"{self.uid[:10]}...{self.uid[-6:]}"


class AttestationBatch(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SIGNED = "signed", "Signed off-chain"
        ANCHORED = "anchored", "Anchored on-chain"
        FAILED = "failed", "Failed"

    merkle_root = models.CharField(max_length=66, unique=True)
    batch_date = models.DateField(unique=True, db_index=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    record_count = models.PositiveIntegerField(default=0)
    records = models.JSONField(default=list, blank=True)
    score_version = models.PositiveSmallIntegerField(default=1)
    prev_batch_root = models.CharField(max_length=66, blank=True)
    signer = models.CharField(max_length=120, blank=True)
    signature = models.CharField(max_length=128, blank=True)
    payload_hash = models.CharField(max_length=66, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    attestations = models.ManyToManyField(
        OffchainAttestation,
        related_name="batches",
        blank=True,
    )
    transaction_hash = models.CharField(max_length=66, blank=True)
    on_chain_uid = models.CharField(max_length=66, blank=True)
    chain_id = models.PositiveIntegerField(default=0)
    timestamped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end"]

    def __str__(self):
        return self.merkle_root

    @property
    def short_root(self):
        return f"{self.merkle_root[:10]}...{self.merkle_root[-6:]}"

    @property
    def basescan_tx_url(self):
        if not self.transaction_hash or self.chain_id != 8453:
            return ""
        return f"https://basescan.org/tx/{self.transaction_hash}"

    @property
    def is_signature_valid(self):
        from integrations.batch_services import verify_batch_signature

        return verify_batch_signature(self)
