from __future__ import annotations

import argparse
import json
from typing import Sequence

from app.config import get_settings
from app.notifications.telegram import (
    TelegramConfigurationError,
    format_job_radar_test_alert,
    list_updates,
    send_message,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telegram helpers for AI Job Radar.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("get-updates", help="List recent bot updates to discover chat IDs.")

    send_test = subcommands.add_parser("send-test", help="Send a test Telegram alert.")
    send_test.add_argument("--chat-id", dest="chat_id", help="Override TELEGRAM_CHAT_ID for this run.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()

    try:
        if args.command == "get-updates":
            updates = list_updates(settings)
            print(
                json.dumps(
                    [
                        {
                            "update_id": update.update_id,
                            "chat_id": update.chat_id,
                            "chat_type": update.chat_type,
                            "username": update.username,
                            "first_name": update.first_name,
                            "title": update.title,
                            "text": update.text,
                        }
                        for update in updates
                    ],
                    indent=2,
                )
            )
            return 0

        if args.command == "send-test":
            response = send_message(settings, format_job_radar_test_alert(), chat_id=args.chat_id)
            print(json.dumps(response, indent=2))
            return 0
    except TelegramConfigurationError as exc:
        parser.exit(status=2, message=f"{exc}\n")

    parser.exit(status=2, message=f"Unknown command: {args.command}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
