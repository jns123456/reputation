from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from integrations.attestation_services import verify_offchain_attestation
from integrations.models import AttestationSchema, OffchainAttestation
from integrations.services import (
    backfill_market_resolved_outcome,
    import_market_from_normalized,
    repair_resolved_markets_with_pending_predictions,
)
from markets.models import Market
from predictions.models import Prediction
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


class ResolvedMarketRepairTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="repair-user", password="pass")
        self.raw_market = {
            "id": "repair-psg",
            "question": "Will Paris Saint-Germain FC win on 2026-05-30?",
            "closed": True,
            "automaticallyResolved": True,
            "umaResolutionStatus": "resolved",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["1", "0"]',
        }

    def test_backfill_scores_pending_forecast_from_stored_raw(self):
        market = Market.objects.create(
            external_id="repair-psg",
            title=self.raw_market["question"],
            slug="repair-psg",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
            resolved_outcome="",
            polymarket_raw=self.raw_market,
        )
        prediction = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )
        market.status = Market.Status.RESOLVED
        market.current_probability = {"Yes": 1.0, "No": 0.0}
        market.save(update_fields=["status", "current_probability", "updated_at"])

        backfill_market_resolved_outcome(market)
        resolve_market_predictions(market)
        prediction.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(market.resolved_outcome, "Yes")
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertTrue(prediction.is_correct)
        self.assertEqual(self.user.profile.reputation_points, 60)

    def test_repair_batch_scores_pending_forecasts(self):
        market = Market.objects.create(
            external_id="repair-batch-1",
            title=self.raw_market["question"],
            slug="repair-batch-1",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
            resolved_outcome="",
            polymarket_raw=self.raw_market,
        )
        prediction = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )
        market.status = Market.Status.RESOLVED
        market.current_probability = {"Yes": 1.0, "No": 0.0}
        market.save(update_fields=["status", "current_probability", "updated_at"])

        result = repair_resolved_markets_with_pending_predictions()
        prediction.refresh_from_db()
        market.refresh_from_db()

        self.assertEqual(result["repaired_markets"], 1)
        self.assertEqual(result["resolved_predictions"], 1)
        self.assertEqual(market.resolved_outcome, "Yes")
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertTrue(prediction.is_correct)

    def test_repair_refreshes_open_market_with_pending_forecasts(self):
        from unittest.mock import patch

        from integrations.polymarket.client import (
            build_polymarket_event_raw,
            normalize_polymarket_event_record,
        )
        from integrations.polymarket.constants import MULTI_OUTCOME_EVENT_KIND
        event_raw = {
            "slug": "league-winner-repair",
            "title": "League Winner",
            "markets": [
                {
                    "id": "1",
                    "question": "Will PSG win?",
                    "outcomes": '["Yes", "No"]',
                    "groupItemTitle": "PSG",
                    "closed": True,
                    "automaticallyResolved": True,
                    "outcomePrices": '["1", "0"]',
                },
                {
                    "id": "2",
                    "question": "Will Arsenal win?",
                    "outcomes": '["Yes", "No"]',
                    "groupItemTitle": "Arsenal",
                    "closed": True,
                    "automaticallyResolved": True,
                    "outcomePrices": '["0", "1"]',
                },
                {
                    "id": "3",
                    "question": "Will Real Madrid win?",
                    "outcomes": '["Yes", "No"]',
                    "groupItemTitle": "Real Madrid",
                    "closed": True,
                    "automaticallyResolved": True,
                    "outcomePrices": '["0", "1"]',
                },
            ],
        }
        market = Market.objects.create(
            external_id="pm-event:league-winner-repair",
            title="League Winner",
            slug="league-winner-repair",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "PSG"}, {"label": "Arsenal"}, {"label": "Real Madrid"}],
            current_probability={"PSG": 0.57},
            resolved_outcome="",
            polymarket_slug="league-winner-repair",
            polymarket_raw={"market_kind": MULTI_OUTCOME_EVENT_KIND},
            polymarket_event_raw=event_raw,
        )
        prediction = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="PSG",
        )

        def _fake_refresh(m):
            normalized = normalize_polymarket_event_record(event_raw, require_open=False)
            raw = build_polymarket_event_raw(event_raw, normalized=normalized)
            updated, _ = import_market_from_normalized(
                normalized, raw_market=raw, raw_event=event_raw
            )
            return updated

        with patch(
            "integrations.services.refresh_market_from_polymarket",
            side_effect=_fake_refresh,
        ):
            result = repair_resolved_markets_with_pending_predictions()

        prediction.refresh_from_db()
        market.refresh_from_db()

        self.assertEqual(result["candidates"], 1)
        self.assertEqual(result["refreshed_markets"], 1)
        self.assertEqual(market.status, Market.Status.RESOLVED)
        self.assertEqual(market.resolved_outcome, "PSG")
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertTrue(prediction.is_correct)


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
