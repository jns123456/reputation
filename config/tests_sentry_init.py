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

    def test_drops_best_effort_celery_enqueue_warnings(self):
        for message in (
            "Failed to enqueue category sync for politics; continuing",
            "Failed to enqueue market refresh for 42; continuing",
            "Failed to enqueue category sync for politics; continuing (ConnectionError: redis ssl eof)",
        ):
            with self.subTest(message=message):
                event = {"logentry": {"message": message}, "logger": "integrations.celery_utils"}
                self.assertIsNone(_before_send(event, {}))

    def test_drops_celery_utils_redis_connection_errors(self):
        event = {
            "logger": "integrations.celery_utils",
            "exception": {
                "values": [
                    {
                        "type": "OperationalError",
                        "value": "Error 8 connecting to redis:18560",
                        "stacktrace": {
                            "frames": [
                                {"module": "integrations.celery_utils", "function": "enqueue_category_sync"},
                            ],
                        },
                    },
                ],
            },
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

    def test_drops_handled_redis_cache_connection_error(self):
        class ConnectionError(Exception):
            pass

        ConnectionError.__module__ = "redis.exceptions"
        event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"filename": "/app/config/cache_backends.py", "lineno": 29},
                            ]
                        }
                    }
                ]
            }
        }
        hint = {"exc_info": (ConnectionError, ConnectionError("reset by peer"), None)}
        self.assertIsNone(_before_send(event, hint))

    def test_drops_handled_redis_cache_out_of_memory_error(self):
        class OutOfMemoryError(Exception):
            pass

        OutOfMemoryError.__module__ = "redis.exceptions"
        event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"filename": "config/cache_backends.py", "lineno": 29},
                            ]
                        }
                    }
                ]
            }
        }
        hint = {"exc_info": (OutOfMemoryError, OutOfMemoryError("maxmemory"), None)}
        self.assertIsNone(_before_send(event, hint))

    def test_keeps_redis_errors_outside_cache_backend(self):
        class ConnectionError(Exception):
            pass

        ConnectionError.__module__ = "redis.exceptions"
        event = {"exception": {"values": [{"stacktrace": {"frames": [{"filename": "celery/worker.py"}]}}]}}
        hint = {"exc_info": (ConnectionError, ConnectionError("broker down"), None)}
        self.assertIs(event, _before_send(event, hint))

    def test_event_message_prefers_logentry(self):
        event = {
            "logentry": {"message": "from logentry"},
            "message": "from top level",
        }
        self.assertEqual(_event_message(event), "from logentry")
