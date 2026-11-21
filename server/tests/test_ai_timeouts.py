"""Regression tests for AI provider timeouts and Android's 60-second deadline."""
import io
import os
import socket
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

os.environ.setdefault("AI_PROVIDER", "gemini")
os.environ.setdefault("NEWS_ENABLED", "false")
os.environ.setdefault("ADMIN_KEY", "")

import server


class GroqTimeoutBudgetTests(unittest.TestCase):
    def setUp(self):
        server.set_gemini_failure(None, None)

    def test_groq_socket_timeout_is_not_retried(self):
        with patch.object(server, "GROQ_API_KEY", "test-groq-key"), \
             patch.object(server.urllib.request, "urlopen", side_effect=socket.timeout("timed out")) as request, \
             patch.object(server.time, "sleep") as sleep:
            answer = server.groq_generate("system", "test message")

        self.assertIsNone(answer)
        request.assert_called_once()
        self.assertLessEqual(request.call_args.kwargs["timeout"], 50)
        sleep.assert_not_called()
        self.assertIn("hết thời gian chờ", server.gemini_failure_reason().lower())

    def test_groq_timeout_configuration_is_capped(self):
        self.assertGreaterEqual(server.GROQ_TIMEOUT_SECONDS, 10)
        self.assertLessEqual(server.GROQ_TIMEOUT_SECONDS, 50)
        self.assertLessEqual(server.GROQ_TOTAL_TIMEOUT_SECONDS, 55)


class GeminiTimeoutBudgetTests(unittest.TestCase):
    def setUp(self):
        server.set_gemini_failure(None, None)

    def test_primary_retry_and_fallback_use_bounded_timeouts(self):
        def unavailable(*args, **kwargs):
            raise HTTPError(args[0].full_url, 503, "Unavailable", {}, io.BytesIO(b"busy"))

        with patch.object(server, "GEMINI_API_KEY", "test-gemini-key"), \
             patch.object(server, "GEMINI_MODEL", "primary-model"), \
             patch.object(server, "GEMINI_FALLBACK_MODEL", "fallback-model"), \
             patch.object(server.urllib.request, "urlopen", side_effect=unavailable) as request, \
             patch.object(server.time, "sleep"):
            answer = server.gemini("system", "test message")

        self.assertIsNone(answer)
        self.assertEqual(request.call_count, 3)
        for call in request.call_args_list:
            self.assertLessEqual(call.kwargs["timeout"], 17)
        self.assertGreaterEqual(server.GEMINI_TIMEOUT_SECONDS, 10)
        self.assertLessEqual(server.GEMINI_TIMEOUT_SECONDS, 17)


if __name__ == "__main__":
    unittest.main()
