# [RUNTIME] Thin OpenAPI HTTP client. P0–P2: JSON + multipart install/upload.
"""
HTTP client for AstrBot OpenAPI v1 (LAN-friendly).

Design notes for later debugging:
  - Auth: OpenAPI lists ApiKeyAuth (header X-API-Key) and BearerAuth.
    Default ASTRBOT_AUTH_MODE=api_key. Use bearer if your instance issues JWT.
    auto: send both when token set (some gateways accept either).
  - Never put token into exception messages or returned JSON.
  - Connection errors are classified (timeout / refused / DNS / TLS / HTTP status)
    so agents can fix LAN routing vs credentials.
  - Mutation gating is NOT in this client — tools call mutation_denied_payload first.
  - install/upload uses multipart (post_multipart); do NOT send ZIP as JSON.
  - stdlib urllib is NOT used as primary path; httpx is declared in requirements.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urljoin

import httpx

from .config import RuntimeConfig, load_config


@dataclass
class ApiResult:
    """Normalized result for MCP tools (always JSON-serializable via to_dict)."""

    ok: bool
    status_code: int | None
    data: Any
    error: str | None
    error_kind: str | None
    url: str | None
    elapsed_ms: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status_code": self.status_code,
            "data": self.data,
            "error": self.error,
            "error_kind": self.error_kind,
            "url": self.url,
            "elapsed_ms": self.elapsed_ms,
        }


def _build_headers(cfg: RuntimeConfig) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "skill-astrbot-plugin-mcp-runtime/0.4-p3",
    }
    if not cfg.token:
        return headers
    mode = cfg.auth_mode
    if mode == "bearer":
        headers["Authorization"] = f"Bearer {cfg.token}"
    elif mode == "auto":
        # [RUNTIME] dual headers: prefer instances that accept either scheme
        headers["X-API-Key"] = cfg.token
        headers["Authorization"] = f"Bearer {cfg.token}"
    else:
        # api_key (default) — matches OpenAPI ApiKeyAuth name=X-API-Key
        headers["X-API-Key"] = cfg.token
    return headers


def _classify_httpx_error(exc: BaseException) -> tuple[str, str]:
    """Return (error_kind, human message) without embedding secrets."""
    if isinstance(exc, httpx.TimeoutException):
        return (
            "timeout",
            "HTTP timeout. Raise ASTRBOT_HTTP_TIMEOUT or check LAN latency / firewall.",
        )
    if isinstance(exc, httpx.ConnectError):
        return (
            "connect",
            "Cannot connect. Check ASTRBOT_BASE_URL host:port, AstrBot running, "
            "same LAN/VPN, and firewall allow inbound to Dashboard port.",
        )
    if isinstance(exc, httpx.ProxyError):
        return ("proxy", f"Proxy error: {exc!s}")
    if isinstance(exc, httpx.NetworkError):
        return ("network", f"Network error: {exc!s}")
    if isinstance(exc, httpx.HTTPError):
        return ("http_client", f"HTTP client error: {type(exc).__name__}: {exc!s}")
    return ("unknown", f"{type(exc).__name__}: {exc!s}")


def _stream_with_deadline(
    client: httpx.Client,
    method: str,
    url: str,
    params: Mapping[str, Any] | None,
    json_body: Any,
    max_total_seconds: float,
) -> tuple[httpx.Response, bool]:
    """Read a streaming response under a hard wall-clock cap.

    httpx's `timeout` is per-operation, so a server that keeps an event stream open
    (or trickles keep-alives) never trips it and the sync read blocks forever — which
    hangs the WHOLE MCP server, since tools run in one process. Chat SSE does exactly
    that. Accumulate with a deadline instead, then build a complete Response from what
    arrived so downstream parsing is unchanged.
    """
    deadline = time.monotonic() + max(0.0, max_total_seconds)
    chunks: list[bytes] = []
    headers: dict[str, str] = {}
    status = 0
    truncated = False

    with client.stream(method, url, params=params, json=json_body) as resp:
        status = resp.status_code
        headers = {k: v for k, v in resp.headers.items()}
        for chunk in resp.iter_bytes():
            chunks.append(chunk)
            if time.monotonic() >= deadline:
                truncated = True
                break

    return (
        httpx.Response(
            status,
            headers=headers,
            content=b"".join(chunks),
            request=httpx.Request(method, url),
        ),
        truncated,
    )


class AstrBotClient:
    """Synchronous client (FastMCP tools are sync-friendly)."""

    def __init__(self, cfg: RuntimeConfig | None = None) -> None:
        self.cfg = cfg or load_config()

    def _url(self, path: str) -> str:
        base = self.cfg.base_url.rstrip("/") + "/"
        return urljoin(base, path.lstrip("/"))

    def _not_configured(self) -> ApiResult:
        return ApiResult(
            ok=False,
            status_code=None,
            data=None,
            error=(
                "Runtime disabled: set ASTRBOT_BASE_URL on the MCP host env "
                "(e.g. http://192.168.x.x:6185 for LAN AstrBot)."
            ),
            error_kind="not_configured",
            url=None,
            elapsed_ms=None,
        )

    def _from_response(self, resp: httpx.Response) -> ApiResult:
        elapsed = None
        try:
            elapsed = float(resp.elapsed.total_seconds() * 1000.0)
        except Exception:
            pass

        body: Any
        text = resp.text or ""
        ctype = (resp.headers.get("content-type") or "").lower()
        # [RUNTIME P3] WebChat often returns SSE (data: {...}) with HTTP 200
        if text.lstrip().startswith("data:") or "text/event-stream" in ctype:
            # Keep enough for multi-event chat; tools truncate for the agent
            body = {"_sse": True, "_raw_text": text[:100000]}
        else:
            try:
                body = resp.json() if text else None
            except json.JSONDecodeError:
                body = {"_raw_text": text[:8000] if text else ""}

        if resp.status_code == 401 or resp.status_code == 403:
            return ApiResult(
                ok=False,
                status_code=resp.status_code,
                data=body,
                error=(
                    "Auth rejected. Set ASTRBOT_TOKEN to Dashboard API key; "
                    "try ASTRBOT_AUTH_MODE=api_key (default) or bearer."
                ),
                error_kind="auth",
                url=str(resp.url),
                elapsed_ms=elapsed,
            )

        if resp.status_code >= 400:
            return ApiResult(
                ok=False,
                status_code=resp.status_code,
                data=body,
                error=f"HTTP {resp.status_code} from AstrBot OpenAPI",
                error_kind="http_status",
                url=str(resp.url),
                elapsed_ms=elapsed,
            )

        return ApiResult(
            ok=True,
            status_code=resp.status_code,
            data=body,
            error=None,
            error_kind=None,
            url=str(resp.url),
            elapsed_ms=elapsed,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        timeout: float | None = None,
        max_total_seconds: float | None = None,
    ) -> ApiResult:
        if not self.cfg.enabled:
            return self._not_configured()

        url = self._url(path)
        t = timeout if timeout is not None else self.cfg.timeout
        truncated = False

        try:
            with httpx.Client(
                timeout=httpx.Timeout(t),
                headers=_build_headers(self.cfg),
                follow_redirects=True,
            ) as client:
                if max_total_seconds is None:
                    resp = client.request(method.upper(), url, params=params, json=json_body)
                else:
                    resp, truncated = _stream_with_deadline(
                        client, method.upper(), url, params, json_body, max_total_seconds
                    )
        except Exception as exc:  # noqa: BLE001 — always return structured error to agent
            kind, msg = _classify_httpx_error(exc)
            return ApiResult(
                ok=False,
                status_code=None,
                data=None,
                error=msg,
                error_kind=kind,
                url=url,
                elapsed_ms=None,
            )

        result = self._from_response(resp)
        if truncated:
            # Surface it instead of pretending the body was complete: callers parsing
            # an event stream would otherwise read a silently short response.
            return ApiResult(
                ok=result.ok,
                status_code=result.status_code,
                data=result.data,
                error=(
                    f"{result.error} | " if result.error else ""
                )
                + f"stream truncated at max_total_seconds={max_total_seconds}",
                error_kind=result.error_kind or "stream_truncated",
                url=result.url,
                elapsed_ms=result.elapsed_ms,
            )
        return result

    def post_multipart(
        self,
        path: str,
        *,
        files: Mapping[str, tuple[str, bytes, str]],
        data: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> ApiResult:
        """
        [RUNTIME P2] multipart/form-data POST (install/upload).

        files: field_name -> (filename, content_bytes, content_type)
        Do not set Content-Type header manually — httpx adds boundary.
        """
        if not self.cfg.enabled:
            return self._not_configured()

        url = self._url(path)
        # [RUNTIME] ZIP upload on LAN may exceed default timeout
        t = timeout if timeout is not None else max(float(self.cfg.timeout), 60.0)
        headers = _build_headers(self.cfg)
        # Accept only; let httpx set multipart Content-Type
        headers.pop("Content-Type", None)

        try:
            with httpx.Client(
                timeout=httpx.Timeout(t),
                headers=headers,
                follow_redirects=True,
            ) as client:
                resp = client.post(url, files=files, data=data)
        except Exception as exc:  # noqa: BLE001
            kind, msg = _classify_httpx_error(exc)
            return ApiResult(
                ok=False,
                status_code=None,
                data=None,
                error=msg,
                error_kind=kind,
                url=url,
                elapsed_ms=None,
            )

        return self._from_response(resp)

    def get(self, path: str, **kwargs: Any) -> ApiResult:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> ApiResult:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> ApiResult:
        return self.request("PATCH", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> ApiResult:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> ApiResult:
        # [RUNTIME P2] Uninstall uses DELETE with optional JSON body
        # (delete_config / delete_data). httpx supports json= on DELETE.
        return self.request("DELETE", path, **kwargs)


def encode_plugin_id(plugin_id: str) -> str:
    """
    [RUNTIME] Path-segment encode plugin ids (safe for / and special chars).

    OpenAPI PluginId is a path param; use quote(..., safe='') so ids with
    odd characters do not break the path. Most ids are astrbot_plugin_*.
    """
    return quote((plugin_id or "").strip(), safe="")
