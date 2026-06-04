from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import CreatorSubscription, SubscriberAudience
from accounts.monetization_services import (
    is_active_subscriber,
    subscribe_to_creator,
    unsubscribe_from_creator,
    update_creator_program,
)
from conftest import create_user
from predictions.models import Prediction
from predictions.services import create_prediction
from markets.models import Market


class MonetizationServiceTests(TestCase):
    def setUp(self):
        self.creator = create_user("creator")
        self.subscriber = create_user("subscriber")
        self.market = Market.objects.create(
            external_id="mon-test-1",
            title="Test market",
            slug="mon-test-market",
            source="polymarket",
            status=Market.Status.OPEN,
            outcomes=["Yes", "No"],
            current_probability={"Yes": 0.5, "No": 0.5},
            accepting_orders=True,
        )
        update_creator_program(
            user=self.creator,
            is_enabled=True,
            tagline="Premium calls",
            welcome_message="Thanks for subscribing.",
            monthly_price_cents=1000,
        )

    def test_subscribe_and_unsubscribe(self):
        subscribe_to_creator(subscriber=self.subscriber, creator=self.creator)
        self.assertTrue(is_active_subscriber(viewer=self.subscriber, creator=self.creator))
        unsubscribe_from_creator(subscriber=self.subscriber, creator=self.creator)
        self.assertFalse(is_active_subscriber(viewer=self.subscriber, creator=self.creator))

    def test_subscriber_only_prediction_gated(self):
        subscribe_to_creator(subscriber=self.subscriber, creator=self.creator)
        prediction = create_prediction(
            user=self.creator,
            market=self.market,
            predicted_outcome="Yes",
            reasoning="Secret thesis",
            audience=SubscriberAudience.SUBSCRIBERS,
        )
        self.assertEqual(prediction.audience, SubscriberAudience.SUBSCRIBERS)

        from accounts.monetization_services import can_view_audience_content

        self.assertFalse(
            can_view_audience_content(
                viewer=create_user("outsider"),
                creator=self.creator,
                audience=SubscriberAudience.SUBSCRIBERS,
            )
        )
        self.assertTrue(
            can_view_audience_content(
                viewer=self.subscriber,
                creator=self.creator,
                audience=SubscriberAudience.SUBSCRIBERS,
            )
        )


class MonetizationViewTests(TestCase):
    def setUp(self):
        self.creator = create_user("creator")
        self.subscriber = create_user("subscriber")
        update_creator_program(
            user=self.creator,
            is_enabled=True,
            tagline="Calls",
            welcome_message="",
            monthly_price_cents=500,
        )
        self.client = Client()

    def test_creator_setup_requires_owner(self):
        self.client.force_login(self.subscriber)
        url = reverse("accounts:creator_setup", kwargs={"username": self.creator.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_subscribe_via_post(self):
        self.client.force_login(self.subscriber)
        response = self.client.post(
            reverse("accounts:creator_subscribe"),
            {"creator_id": self.creator.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CreatorSubscription.objects.filter(
                creator=self.creator,
                subscriber=self.subscriber,
                status=CreatorSubscription.Status.ACTIVE,
            ).exists()
        )

    def test_monetize_dashboard_shows_subscriber_count_for_owner(self):
        subscribe_to_creator(subscriber=self.subscriber, creator=self.creator)
        self.client.force_login(self.creator)
        response = self.client.get(
            reverse("accounts:profile_monetize", kwargs={"username": self.creator.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Creator dashboard")
        self.assertContains(response, "1")
