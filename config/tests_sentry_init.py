from django.test import SimpleTestCase

from config.sentry_init import _before_send, _event_message


class SentryBeforeSendTests(SimpleTestCase):
    def test_drops_worker_lost_error(self):
        class WorkerLostError(Exception):
            pass

        event = {"message": "worker lost"}
        hint = {"exc_info": (WorkerLostError, WorkerLostError(), None)}
        self.assertIsNone(_before_send(event, hint))

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

    def test_drops_sigterm_without_multiprocessing_logger(self):
        event = {
            "logentry": {
                "message": "Process 'ForkPoolWorker-1' pid:11 exited with 'signal 15 (SIGTERM)'"
            }
        }
        self.assertIsNone(_before_send(event, {}))

    def test_keeps_other_multiprocessing_errors(self):
        event = {
            "logger": "multiprocessing",
            "message": "Process 'MainProcess' pid:1 crashed",
        }
        self.assertIs(_before_send(event, {}), event)

    def test_keeps_unrelated_errors(self):
        event = {"message": "Something broke", "logentry": {"message": "ValueError"}}
        hint = {"exc_info": (ValueError, ValueError("boom"), None)}
        self.assertIs(event, _before_send(event, hint))

    def test_event_message_prefers_logentry(self):
        event = {
            "logentry": {"message": "from logentry"},
            "message": "from top level",
        }
        self.assertEqual(_event_message(event), "from logentry")
