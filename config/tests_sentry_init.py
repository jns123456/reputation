from django.test import SimpleTestCase

from config.sentry_init import _before_send, _event_message


class SentryBeforeSendTests(SimpleTestCase):
    def test_drops_celery_worker_sigterm(self):
        event = {
            "logger": "multiprocessing",
            "logentry": {
                "message": (
                    "Process 'ForkPoolWorker-1' pid:11 exited with "
                    "'signal 15 (SIGTERM)'"
                ),
            },
        }
        self.assertIsNone(_before_send(event, {}))

    def test_keeps_other_multiprocessing_errors(self):
        event = {
            "logger": "multiprocessing",
            "message": "Process 'MainProcess' pid:1 crashed",
        }
        self.assertIs(_before_send(event, {}), event)

    def test_keeps_non_multiprocessing_errors(self):
        event = {
            "logger": "celery.worker",
            "message": "ForkPoolWorker-1 exited with SIGTERM",
        }
        self.assertIs(_before_send(event, {}), event)

    def test_event_message_prefers_logentry(self):
        event = {
            "logentry": {"message": "from logentry"},
            "message": "from top level",
        }
        self.assertEqual(_event_message(event), "from logentry")
