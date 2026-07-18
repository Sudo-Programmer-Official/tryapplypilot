from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import get_settings
from app.notifications.telegram import (
    TelegramConfigurationError,
    TelegramUpdate,
    _decode_response,
    format_job_radar_test_alert,
    list_updates,
)


class TelegramTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_format_job_radar_test_alert_mentions_next_step(self) -> None:
        message = format_job_radar_test_alert()
        self.assertIn("AI Job Radar test alert", message)
        self.assertIn("live collector loop", message.casefold())

    def test_decode_response_rejects_unsuccessful_payload(self) -> None:
        with self.assertRaisesRegex(Exception, "Telegram API returned an error"):
            _decode_response(b'{"ok": false, "description": "bad request"}')

    def test_list_updates_parses_message_updates(self) -> None:
        payload = b"""{
          "ok": true,
          "result": [
            {
              "update_id": 1,
              "message": {
                "text": "/start",
                "chat": {
                  "id": 12345,
                  "type": "private",
                  "username": "abhishek",
                  "first_name": "Abhishek"
                }
              }
            }
          ]
        }"""

        class _FakeResponse:
            def __enter__(self) -> _FakeResponse:
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return payload

        with patch("app.notifications.telegram.urlopen", return_value=_FakeResponse()):
            settings = get_settings()
            updates = list_updates(settings)

        self.assertEqual(
            updates,
            [
                TelegramUpdate(
                    update_id=1,
                    chat_id="12345",
                    chat_type="private",
                    text="/start",
                    username="abhishek",
                    first_name="Abhishek",
                    title=None,
                )
            ],
        )

    def test_get_settings_exposes_telegram_configuration(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "bot-token",
                "TELEGRAM_CHAT_ID": "12345",
                "TELEGRAM_API_BASE_URL": "https://api.telegram.org",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            settings = get_settings()

        self.assertTrue(settings.telegram.bot_configured)
        self.assertTrue(settings.telegram.delivery_configured)
        self.assertEqual(settings.telegram.chat_id, "12345")
        self.assertEqual(settings.telegram.api_base_url, "https://api.telegram.org")


if __name__ == "__main__":
    unittest.main()
