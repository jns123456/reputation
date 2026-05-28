from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from integrations.attestation_services import verify_offchain_attestation
from integrations.models import AttestationSchema, OffchainAttestation
from integrations.services import import_market_from_normalized
from markets.models import Market
from predictions.services import create_prediction, resolve_market_predictions
from reputation.models import ReputationEvent


class MarketImportServiceTests(TestCase):
    def test_import_creates_market(self):
        data = {
            "external_id": "import-1",
            "title": "Imported Market",
            "description": "Desc",
            "category": "Tech",
            "source": "polymarket",
            "status": "open",
            "outcomes": [{"label": "Yes"}, {"label": "No"}],
            "current_probability": {"Yes": 0.5, "No": 0.5},
            "close_date": None,
            "resolution_date": None,
            "resolved_outcome": "",
        }
        market, created = import_market_from_normalized(data)
        self.assertTrue(created)
        self.assertEqual(market.external_id, "import-1")
        self.assertTrue(market.slug)

    def test_import_updates_existing(self):
        data = {
            "external_id": "import-2",
            "title": "Original",
            "description": "",
            "category": "",
            "source": "polymarket",
            "status": "open",
            "outcomes": [],
            "current_probability": {},
            "close_date": None,
            "resolution_date": None,
            "resolved_outcome": "",
        }
        import_market_from_normalized(data)
        data["title"] = "Updated Title"
        market, created = import_market_from_normalized(data)
        self.assertFalse(created)
        self.assertEqual(market.title, "Updated Title")


class OffchainAttestationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="attester", password="pass")
        self.market = Market.objects.create(
            external_id="attestation-m1",
            title="Attestation test",
            slug="attestation-test",
            source=Market.Source.MANUAL,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )

    def test_prediction_creation_records_verified_claim_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            prediction = create_prediction(
                user=self.user,
                market=self.market,
                predicted_outcome="Yes",
            )

        attestation = prediction.verified_attestation

        self.assertIsNotNone(attestation)
        self.assertEqual(attestation.schema.kind, AttestationSchema.Kind.PREDICTION_CLAIM)
        self.assertTrue(verify_offchain_attestation(attestation))
        self.assertEqual(attestation.payload["prediction_id"], prediction.id)

    def test_resolution_records_resolution_and_reputation_attestations(self):
        with self.captureOnCommitCallbacks(execute=True):
            prediction = create_prediction(
                user=self.user,
                market=self.market,
                predicted_outcome="Yes",
            )
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save(update_fields=["status", "resolved_outcome"])

        with self.captureOnCommitCallbacks(execute=True):
            resolve_market_predictions(self.market)

        prediction.refresh_from_db()
        reputation_event = ReputationEvent.objects.get(prediction=prediction)
        resolution = OffchainAttestation.objects.get(
            prediction=prediction,
            schema__kind=AttestationSchema.Kind.PREDICTION_RESOLUTION,
        )
        reputation = OffchainAttestation.objects.get(reputation_event=reputation_event)

        self.assertTrue(verify_offchain_attestation(resolution))
        self.assertTrue(verify_offchain_attestation(reputation))
        self.assertEqual(reputation.payload["prediction_uid"], prediction.verified_attestation.uid)

    def test_market_detail_displays_subtle_verified_record_badge(self):
        with self.captureOnCommitCallbacks(execute=True):
            create_prediction(
                user=self.user,
                market=self.market,
                predicted_outcome="Yes",
            )

        response = self.client.get("/markets/attestation-test/")

        self.assertContains(response, "Verified record")

    def test_backfill_command_creates_records_for_existing_forecasts(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.assertIsNone(prediction.verified_attestation)

        call_command("backfill_offchain_attestations")

        prediction.refresh_from_db()
        self.assertIsNotNone(prediction.verified_attestation)

    def test_attestation_detail_displays_timestamp_labels(self):
        with self.captureOnCommitCallbacks(execute=True):
            prediction = create_prediction(
                user=self.user,
                market=self.market,
                predicted_outcome="Yes",
            )
        attestation = prediction.verified_attestation

        response = self.client.get(f"/proof/attestations/{attestation.uid}/")

        self.assertContains(response, "Offchain timestamp")
        self.assertContains(response, "Event timestamp")
