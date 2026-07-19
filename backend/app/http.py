from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import truststore
except ImportError:  # pragma: no cover - fallback when dependency is unavailable
    truststore = None


class HttpClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpTlsSettings:
    ca_bundle_path: Path | None
    skip_ssl_verify: bool


def build_ssl_context(tls: HttpTlsSettings) -> ssl.SSLContext:
    if tls.skip_ssl_verify:
        return ssl._create_unverified_context()
    if tls.ca_bundle_path is not None:
        return ssl.create_default_context(cafile=str(tls.ca_bundle_path))
    if truststore is not None:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ssl.create_default_context()


def _request_text(
    method: str,
    url: str,
    *,
    timeout_seconds: int,
    tls: HttpTlsSettings,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | list[object] | None = None,
) -> str:
    payload_bytes = None
    request_headers = dict(headers or {})
    if body is not None:
        payload_bytes = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(url, data=payload_bytes, headers=request_headers, method=method.upper())
    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
            context=build_ssl_context(tls),
        ) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HttpClientError(f"{method.upper()} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise HttpClientError(f"{method.upper()} {url} failed: {exc.reason}") from exc


def request_text(
    method: str,
    url: str,
    *,
    timeout_seconds: int,
    tls: HttpTlsSettings,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | list[object] | None = None,
) -> str:
    return _request_text(
        method,
        url,
        timeout_seconds=timeout_seconds,
        tls=tls,
        headers=headers,
        body=body,
    )


def request_json(
    method: str,
    url: str,
    *,
    timeout_seconds: int,
    tls: HttpTlsSettings,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | list[object] | None = None,
) -> object:
    response_body = _request_text(
        method,
        url,
        timeout_seconds=timeout_seconds,
        tls=tls,
        headers=headers,
        body=body,
    )
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise HttpClientError(f"{method.upper()} {url} returned invalid JSON.") from exc
