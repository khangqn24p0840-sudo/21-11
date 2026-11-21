from pathlib import Path

ROOT = Path("server")


def replace_once(path: str, old: str, new: str) -> None:
    file = ROOT / path
    encoding = "utf-8-sig" if file.suffix.lower() == ".ps1" else "utf-8"
    source = file.read_text(encoding=encoding)
    count = source.count(old)
    if count == 0 and new in source:
        return
    if count != 1:
        raise SystemExit(f"Expected exactly one match in {file}, got {count}")
    file.write_text(source.replace(old, new, 1), encoding=encoding)


replace_once(
    "server.py",
    '''GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b").strip()
try:
    GROQ_TIMEOUT_SECONDS = max(20, min(int(os.environ.get("GROQ_TIMEOUT_SECONDS", "120")), 300))
except (TypeError, ValueError):
    GROQ_TIMEOUT_SECONDS = 120
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()  # Chỉ dùng khi AI_PROVIDER=gemini.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip()
''',
    '''GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b").strip()
# Android Api.kt waits at most 60 seconds for an HTTP response.
# Keep provider calls and retries within the Android client deadline.
try:
    GROQ_TIMEOUT_SECONDS = max(10, min(int(os.environ.get("GROQ_TIMEOUT_SECONDS", "45")), 50))
except (TypeError, ValueError):
    GROQ_TIMEOUT_SECONDS = 45
GROQ_TOTAL_TIMEOUT_SECONDS = 55  # Leave time for Flask/HTTPS response overhead.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()  # Chỉ dùng khi AI_PROVIDER=gemini.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip()
try:
    GEMINI_TIMEOUT_SECONDS = max(10, min(int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "15")), 17))
except (TypeError, ValueError):
    GEMINI_TIMEOUT_SECONDS = 15
'''
)

replace_once(
    "server.py",
    '''    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=GROQ_TIMEOUT_SECONDS) as response:
''',
    '''    deadline = time.monotonic() + GROQ_TOTAL_TIMEOUT_SECONDS
    for attempt in range(2):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            set_gemini_failure("Groq đã vượt ngân sách thời gian chờ của máy chủ (55 giây).")
            return None
        call_timeout = min(float(GROQ_TIMEOUT_SECONDS), remaining)
        try:
            with urllib.request.urlopen(req, timeout=call_timeout) as response:
'''
)

replace_once(
    "server.py",
    '''            if attempt == 0 and exc.code in retryable_codes:
                time.sleep(1.0)
                continue
''',
    '''            # Retry only while enough time remains for another bounded attempt.
            if attempt == 0 and exc.code in retryable_codes and deadline - time.monotonic() > 2.0:
                time.sleep(min(1.0, max(0.0, deadline - time.monotonic() - 1.0)))
                continue
'''
)

replace_once(
    "server.py",
    '''        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as exc:
            app.logger.warning(
                "Không kết nối được Groq model %s (lần %s/2): %s",
                model, attempt + 1, type(exc).__name__,
            )
            if attempt == 0:
                time.sleep(1.0)
                continue
            set_gemini_failure(
                f"Không kết nối được Groq sau 2 lần thử: {type(exc).__name__}. "
                "Kiểm tra mạng, DNS, tường lửa và thời gian chờ."
            )
            return None
''',
    '''        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as exc:
            underlying = getattr(exc, "reason", None)
            timed_out = isinstance(exc, (TimeoutError, socket.timeout)) or isinstance(
                underlying, (TimeoutError, socket.timeout)
            )
            app.logger.warning(
                "Kết nối Groq model %s thất bại (lần %s/2): %s",
                model, attempt + 1, type(exc).__name__,
            )
            # Retrying a socket timeout can make Android's 60-second read timeout fire first.
            if attempt == 0 and not timed_out and deadline - time.monotonic() > 2.0:
                time.sleep(min(0.5, max(0.0, deadline - time.monotonic() - 1.0)))
                continue
            if timed_out:
                set_gemini_failure(
                    f"Groq hết thời gian chờ sau tối đa {call_timeout:.0f} giây. "
                    "Máy chủ đã dừng thử lại để kịp trả lỗi cho ứng dụng Android."
                )
            else:
                set_gemini_failure(
                    f"Không kết nối được Groq: {type(exc).__name__}. "
                    "Kiểm tra mạng, DNS và tường lửa."
                )
            return None
'''
)

replace_once(
    "server.py",
    "with urllib.request.urlopen(req, timeout=20) as response:",
    "with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT_SECONDS) as response:"
)
replace_once(
    "server.py",
    '''"""Validate and bound Gemini's structured risk result before returning it to the app."""''',
    '''"""Validate and bound the configured provider's structured risk result before returning it to the app."""'''
)
replace_once(
    "server.py",
    'raise ApiError("Ch?a c? n?i dung ?? ph?n t?ch")',
    'raise ApiError("Chưa có nội dung để phân tích")'
)
replace_once(
    "chay.ps1",
    "$env:GROQ_TIMEOUT_SECONDS = '120'",
    "$env:GROQ_TIMEOUT_SECONDS = '45'"
)

readme = ROOT / "README.md"
readme_text = readme.read_text(encoding="utf-8")
anchor = "Groq dùng API tương thích OpenAI tại"
if "Thời gian chờ được căn theo Android" not in readme_text:
    lines = readme_text.splitlines()
    idx = next((i for i, line in enumerate(lines) if line.startswith(anchor)), None)
    if idx is None:
        raise SystemExit("README insertion point was not found")
    lines[idx + 1:idx + 1] = [
        "",
        "**Thời gian chờ được căn theo Android:** app chờ tối đa 60 giây. Groq dùng timeout mặc định 45 giây, giới hạn tối đa 50 giây và tổng thời gian thử lại tối đa 55 giây; lỗi timeout mạng không bị gọi lại. Gemini dùng 15 giây mỗi lượt, tối đa 17 giây; hai lần thử model chính và một model dự phòng vẫn nằm trong ngân sách phản hồi.",
        "",
    ]
    readme_text = "\n".join(lines) + "\n"
readme_text = readme_text.replace("GROQ_TIMEOUT_SECONDS=120", "GROQ_TIMEOUT_SECONDS=45")
if "GEMINI_TIMEOUT_SECONDS=15" not in readme_text:
    readme_text = readme_text.replace("GROQ_TIMEOUT_SECONDS=45\n", "GROQ_TIMEOUT_SECONDS=45\nGEMINI_TIMEOUT_SECONDS=15\n", 1)
readme.write_text(readme_text, encoding="utf-8")

test_source = '''"""Regression tests for AI provider timeouts and Android's 60-second deadline."""
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
        with patch.object(server, "GROQ_API_KEY", "test-groq-key"), \\
             patch.object(server.urllib.request, "urlopen", side_effect=socket.timeout("timed out")) as request, \\
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

        with patch.object(server, "GEMINI_API_KEY", "test-gemini-key"), \\
             patch.object(server, "GEMINI_MODEL", "primary-model"), \\
             patch.object(server, "GEMINI_FALLBACK_MODEL", "fallback-model"), \\
             patch.object(server.urllib.request, "urlopen", side_effect=unavailable) as request, \\
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
'''
test_path = ROOT / "tests" / "test_ai_timeouts.py"
test_path.parent.mkdir(parents=True, exist_ok=True)
if not test_path.exists():
    test_path.write_text(test_source, encoding="utf-8")
elif "GroqTimeoutBudgetTests" not in test_path.read_text(encoding="utf-8"):
    raise SystemExit("A different test_ai_timeouts.py already exists")

print("Applied bounded AI timeouts, clearer Vietnamese validation text, and regression tests.")
