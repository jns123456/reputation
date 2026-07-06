from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from conftest import create_user
from integrations.polymarket.client import (
    build_polymarket_event_raw,
    normalize_polymarket_event_record,
)
from integrations.polymarket.constants import MULTI_OUTCOME_EVENT_KIND, POLYMARKET_EVENT_EXTERNAL_PREFIX
from markets.models import Market
from predictions.incident_notice_services import (
    F1_PODIUM_INCIDENT_SESSION_KEY,
    F1_PODIUM_MARKET_SLUG,
    backfill_f1_podium_incident_notices,
    dismiss_f1_podium_incident_notice,
    queue_f1_podium_incident_notice,
    user_dismissed_f1_podium_incident_notice,
)
from predictions.models import Prediction
from predictions.services import repair_misscored_multi_binary_predictions

User = get_user_model()


def _podium_bucket(driver, *, yes_price, closed=False, resolved=False):
    market = {
        "id": f"podium-{driver.lower().replace(' ', '-')}",
        "question": f"Will {driver} finish on the podium?",
        "outcomes": '["Yes", "No"]',
        "groupItemTitle": driver,
        "groupItemThreshold": "0",
        "outcomePrices": f'["{yes_price}", "{1 - yes_price}"]',
        "closed": closed,
    }
    if resolved:
        market["automaticallyResolved"] = True
        market["umaResolutionStatus"] = "resolved"
    return market


F1_PODIUM_RESOLVED = {
    "slug": F1_PODIUM_MARKET_SLUG,
    "title": "British Grand Prix: Driver Podium Finish",
    "endDate": "2026-07-12T14:00:00Z",
    "markets": [
        _podium_bucket("Lewis Hamilton", yes_price=1.0, closed=True, resolved=True),
        _podium_bucket("George Russell", yes_price=1.0, closed=True, resolved=True),
        _podium_bucket("Charles Leclerc", yes_price=1.0, closed=True, resolved=True),
        _podium_bucket("Max Verstappen", yes_price=0.0, closed=True, resolved=True),
    ],
}


@override_settings(WEEKLY_CONTEST_ENABLED=False)
class F1PodiumIncidentNoticeTests(TestCase):
    def setUp(self):
        cache.clear()
        normalized = normalize_polymarket_event_record(F1_PODIUM_RESOLVED)
        raw = build_polymarket_event_raw(F1_PODIUM_RESOLVED, normalized=normalized)
        self.market = Market.objects.create(
            external_id=f"{POLYMARKET_EVENT_EXTERNAL_PREFIX}{F1_PODIUM_MARKET_SLUG}",
            polymarket_slug=F1_PODIUM_MARKET_SLUG,
            title=normalized["title"],
            slug="f1-british-podium-test",
            source=Market.Source.POLYMARKET,
            status=Market.Status.RESOLVED,
            outcomes=normalized["outcomes"],
            current_probability=normalized["current_probability"],
            resolved_outcome=normalized["resolved_outcome"],
            polymarket_raw={**raw, "market_kind": MULTI_OUTCOME_EVENT_KIND},
            polymarket_event_raw=F1_PODIUM_RESOLVED,
        )
        self.user = create_user(username="f1-incident-user")
        self.prediction = Prediction.objects.create(
            user=self.user,
            market=self.market,
            predicted_outcome="Charles Leclerc",
            predicted_direction=Prediction.Direction.YES,
            probability_at_prediction_time={"Charles Leclerc": 0.42},
            status=Prediction.Status.RESOLVED,
            is_correct=False,
        )

    def test_backfill_queues_notice_for_affected_user(self):
        queued = backfill_f1_podium_incident_notices()
        self.assertEqual(queued, [self.user.id])

    def test_modal_shows_once_after_login(self):
        queue_f1_podium_incident_notice(user_id=self.user.id)
        session = self.client.session
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertContains(response, "f1-podium-incident-modal-title")
        self.assertContains(response, "Charles Leclerc")

        response = self.client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertNotContains(response, "f1-podium-incident-modal-title")

    def test_dismiss_prevents_future_notices(self):
        dismiss_f1_podium_incident_notice(user=self.user)
        self.assertTrue(user_dismissed_f1_podium_incident_notice(self.user))

        session = self.client.session
        session[F1_PODIUM_INCIDENT_SESSION_KEY] = {"prediction_id": self.prediction.id}
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertNotContains(response, "f1-podium-incident-modal-title")

    def test_dismiss_endpoint(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("dashboard:dismiss_f1_podium_incident_notice"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertTrue(user_dismissed_f1_podium_incident_notice(self.user))

    def test_repair_queues_incident_notice(self):
        repair_misscored_multi_binary_predictions()
        self.prediction.refresh_from_db()
        self.assertTrue(self.prediction.is_correct)

        session = self.client.session
        session.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertContains(response, "f1-podium-incident-modal-title")

    def test_modal_renders_in_spanish(self):
        queue_f1_podium_incident_notice(user_id=self.user.id)
        session = self.client.session
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("dashboard:reputation_leaderboard"),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertContains(response, "Aviso de la plataforma")
        self.assertContains(response, "Entendido")
        self.assertNotContains(response, "Got it")
