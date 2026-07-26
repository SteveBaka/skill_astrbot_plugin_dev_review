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
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.parse import quote, urljoin

import httpx

from .config import RuntimeConfig, load_config


@dataclass
class ApiResult:
    """Normalized result for MCP tools (always JSON-serializable via to_dict)."""

    ok: bool
    status_code: Optional[int]
    data: Any
    error: Optional[str]
    error_kind: Optional[str]
    url: Optional[str]
    elapsed_ms: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "status_code": self.status_code,
            "data": self.data,
            "error": self.error,
            "error_kind": self.error_kind,
            "url": self.url,
            "elapsed_ms": self.elapsed_ms,
        }


def _build_headers(cfg: RuntimeConfig) -> Dict[str, str]:
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


class AstrBotClient:
    """Synchronous client (FastMCP tools are sync-friendly)."""

    def __init__(self, cfg: Optional[RuntimeConfig] = None) -> None:
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
        params: Optional[Mapping[str, Any]] = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> ApiResult:
        if not self.cfg.enabled:
            return self._not_configured()

        url = self._url(path)
        t = timeout if timeout is not None else self.cfg.timeout

        try:
            with httpx.Client(
                timeout=httpx.Timeout(t),
                headers=_build_headers(self.cfg),
                follow_redirects=True,
            ) as client:
                resp = client.request(method.upper(), url, params=params, json=json_body)
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

        return self._from_response(resp)

    def post_multipart(
        self,
        path: str,
        *,
        files: Mapping[str, Tuple[str, bytes, str]],
        data: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
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
