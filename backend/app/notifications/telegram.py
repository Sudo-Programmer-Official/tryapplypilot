from __future__ import annotations

from dataclasses import dataclass
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import AppSettings

try:
    import truststore
except ImportError:  # pragma: no cover - fallback when dependency is unavailable
    truststore = None


class TelegramConfigurationError(RuntimeError):
    pass


class TelegramDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramUpdate:
    update_id: int
    chat_id: str
    chat_type: str
    text: str | None
    username: str | None
    first_name: str | None
    title: str | None


def format_job_radar_test_alert() -> str:
    return "\n".join(
        [
            "🚨 AI Job Radar test alert",
            "",
            "Source: Telegram integration",
            "Status: Bot is reachable",
            "Next step: wire the live collector loop so real job alerts land here.",
        ]
    )


def _require_bot_token(settings: AppSettings) -> str:
    token = settings.telegram.bot_token
    if not token:
        raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is not configured.")
    return token


def _require_chat_id(settings: AppSettings, chat_id: str | None) -> str:
    resolved_chat_id = chat_id or settings.telegram.chat_id
    if not resolved_chat_id:
        raise TelegramConfigurationError("TELEGRAM_CHAT_ID is not configured.")
    return resolved_chat_id


def _build_api_url(settings: AppSettings, method: str, query: dict[str, str] | None = None) -> str:
    token = _require_bot_token(settings)
    base_url = settings.telegram.api_base_url.rstrip("/")
    url = f"{base_url}/bot{token}/{method}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def _decode_response(response_body: bytes) -> dict[str, object]:
    payload = json.loads(response_body.decode("utf-8"))
    if not payload.get("ok", False):
        raise TelegramDeliveryError(f"Telegram API returned an error: {payload!r}")
    return payload


def _build_ssl_context(settings: AppSettings) -> ssl.SSLContext:
    if settings.telegram.skip_ssl_verify:
        return ssl._create_unverified_context()
    if settings.telegram.ca_bundle_path is not None:
        return ssl.create_default_context(cafile=str(settings.telegram.ca_bundle_path))
    if truststore is not None:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ssl.create_default_context()


def send_message(
    settings: AppSettings,
    text: str,
    chat_id: str | None = None,
    *,
    parse_mode: str | None = None,
) -> dict[str, object]:
    destination = _require_chat_id(settings, chat_id)
    payload: dict[str, object] = {
        "chat_id": destination,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    request = Request(
        _build_api_url(settings, "sendMessage"),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(
            request,
            timeout=settings.connectors.request_timeout_seconds,
            context=_build_ssl_context(settings),
        ) as response:
            return _decode_response(response.read())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise TelegramDeliveryError(f"Telegram sendMessage failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise TelegramDeliveryError(f"Telegram sendMessage failed: {exc.reason}") from exc


def list_updates(settings: AppSettings) -> list[TelegramUpdate]:
    request = Request(_build_api_url(settings, "getUpdates"), method="GET")
    try:
        with urlopen(
            request,
            timeout=settings.connectors.request_timeout_seconds,
            context=_build_ssl_context(settings),
        ) as response:
            payload = _decode_response(response.read())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise TelegramDeliveryError(f"Telegram getUpdates failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise TelegramDeliveryError(f"Telegram getUpdates failed: {exc.reason}") from exc

    updates: list[TelegramUpdate] = []
    for item in payload.get("result", []):
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not isinstance(message, dict):
            continue
        chat = message.get("chat")
        if not isinstance(chat, dict):
            continue
        updates.append(
            TelegramUpdate(
                update_id=int(item.get("update_id", 0)),
                chat_id=str(chat.get("id", "")),
                chat_type=str(chat.get("type", "")),
                text=message.get("text") if isinstance(message.get("text"), str) else None,
                username=chat.get("username") if isinstance(chat.get("username"), str) else None,
                first_name=chat.get("first_name") if isinstance(chat.get("first_name"), str) else None,
                title=chat.get("title") if isinstance(chat.get("title"), str) else None,
            )
        )
    return updates
