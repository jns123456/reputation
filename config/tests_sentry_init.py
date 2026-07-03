from unittest.mock import patch

from django.test import SimpleTestCase

from config.sentry_init import _before_send, _event_message, init_sentry


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

    def test_drops_exitcode_15_fork_pool_worker(self):
        event = {
            "logger": "multiprocessing",
            "logentry": {
                "message": "Process 'ForkPoolWorker-9' pid:33 exited with 'exitcode 15'",
            },
        }
        self.assertIsNone(_before_send(event, {}))

    def test_drops_gunicorn_worker_sigterm(self):
        event = {
            "logger": "gunicorn.error",
            "logentry": {"message": "Worker (pid:10) was sent SIGTERM!"},
        }
        self.assertIsNone(_before_send(event, {}))

    def test_keeps_other_gunicorn_errors(self):
        event = {
            "logger": "gunicorn.error",
            "logentry": {"message": "Worker (pid:10) exited with code 1"},
        }
        self.assertIs(event, _before_send(event, {}))

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

    def test_drops_transient_polymarket_fetch_timeouts(self):
        class ReadTimeout(Exception):
            pass

        ReadTimeout.__module__ = "requests.exceptions"
        event = {
            "logger": "integrations.services",
            "logentry": {"message": "Failed to fetch World Cup match event fifwc-can-qat-2026-06-18"},
            "exception": {
                "values": [
                    {
                        "type": "ReadTimeout",
                        "stacktrace": {
                            "frames": [
                                {"module": "integrations.polymarket.client", "function": "fetch_event_by_slug"},
                            ],
                        },
                    },
                ],
            },
        }
        hint = {"exc_info": (ReadTimeout, ReadTimeout("read timed out"), None)}
        self.assertIsNone(_before_send(event, hint))

    def test_drops_transient_polymarket_fetch_500_errors(self):
        class HTTPError(Exception):
            pass

        HTTPError.__module__ = "requests.exceptions"

        class FakeResponse:
            status_code = 500

        event = {
            "logger": "integrations.services",
            "logentry": {
                "message": "Failed to fetch Polymarket event fifwc-prt-cdr-2026-06-17-saves-jose-sa-gte4",
            },
            "exception": {
                "values": [
                    {
                        "type": "HTTPError",
                        "value": (
                            "500 Server Error: Internal Server Error for url: "
                            "https://gamma-api.polymarket.com/events/slug/demo"
                        ),
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": "integrations.polymarket.client",
                                    "function": "fetch_event_by_slug",
                                },
                            ],
                        },
                    },
                ],
            },
        }
        exc = HTTPError("500 Server Error")
        exc.response = FakeResponse()
        hint = {"exc_info": (HTTPError, exc, None)}
        self.assertIsNone(_before_send(event, hint))

    def test_drops_http_error_when_status_code_not_in_exc_info(self):
        event = {
            "logger": "integrations.services",
            "logentry": {"message": "Failed to fetch Polymarket event demo-slug"},
            "exception": {
                "values": [
                    {
                        "type": "HTTPError",
                        "value": (
                            "500 Server Error: Internal Server Error for url: "
                            "https://gamma-api.polymarket.com/events/slug/demo"
                        ),
                    },
                ],
            },
        }
        self.assertIsNone(_before_send(event, {}))

    def test_drops_transient_polymarket_sync_timeouts(self):
        class ReadTimeout(Exception):
            pass

        ReadTimeout.__module__ = "requests.exceptions"
        event = {
            "logger": "integrations.sync",
            "logentry": {"message": "H2H/F1 sports sync failed for category sports"},
            "exception": {
                "values": [
                    {
                        "type": "ReadTimeout",
                        "stacktrace": {
                            "frames": [
                                {"module": "integrations.polymarket.client", "function": "fetch_events"},
                            ],
                        },
                    },
                ],
            },
        }
        hint = {"exc_info": (ReadTimeout, ReadTimeout("read timed out"), None)}
        self.assertIsNone(_before_send(event, hint))

    def test_drops_transient_polymarket_chart_timeouts(self):
        class ReadTimeout(Exception):
            pass

        ReadTimeout.__module__ = "requests.exceptions"
        event = {
            "logger": "integrations.polymarket.chart",
            "logentry": {
                "message": "Failed to fetch Polymarket price history for 47919384150197589232393964585899333320474050683727294311209365244400038751833",
            },
            "exception": {
                "values": [
                    {
                        "type": "ReadTimeout",
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": "integrations.polymarket.chart",
                                    "function": "_fetch_price_points",
                                },
                            ],
                        },
                    },
                ],
            },
        }
        hint = {"exc_info": (ReadTimeout, ReadTimeout("read timed out"), None)}
        self.assertIsNone(_before_send(event, hint))

    def test_drops_embedded_sync_transient_db_errors(self):
        event = {
            "logger": "integrations.market_sync_scheduler",
            "logentry": {"message": "Embedded market sync loop failed"},
            "exception": {
                "values": [
                    {
                        "type": "OperationalError",
                        "value": "consuming input failed: SSL error: unexpected eof while reading",
                    },
                ],
            },
        }
        self.assertIsNone(_before_send(event, {}))

    def test_keeps_embedded_sync_non_db_errors(self):
        event = {
            "logger": "integrations.market_sync_scheduler",
            "logentry": {"message": "Embedded market sync loop failed"},
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "unexpected config",
                    },
                ],
            },
        }
        self.assertIs(event, _before_send(event, {}))

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

    @patch("config.sentry_init.settings")
    def test_init_ignores_multiprocessing_logger(self, mock_settings):
        mock_settings.SENTRY_DSN = "https://example@o0.ingest.sentry.io/0"
        mock_settings.SENTRY_ENVIRONMENT = "test"
        mock_settings.SENTRY_TRACES_SAMPLE_RATE = 0.0

        with patch("sentry_sdk.integrations.logging.ignore_logger") as ignore_logger:
            init_sentry()
            ignore_logger.assert_any_call("multiprocessing")
