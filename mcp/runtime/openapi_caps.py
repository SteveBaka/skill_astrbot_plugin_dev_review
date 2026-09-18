# [RUNTIME] OpenAPI capability matrix + graceful degradation for newer endpoints.
"""
Detect whether the connected AstrBot OpenAPI exposes optional/newer plugin
endpoints (4.28-era install/url, plugin update, …) and degrade cleanly on
older cores instead of hard-failing agents.

Resolution order for path presence:
  1. Live `GET {base}/openapi.json` (if AstrBot serves a public spec) — cache
  2. Local snapshot `AstrBot OpenAPI v1.json` at repo root (gitignored)
  3. Feature matrix `min_core` vs running core version (hint only)
  4. Unknown → tools may still attempt the call; HTTP 404 is classified as
     `openapi_unsupported`

Never log tokens. Snapshot/live path sets store path templates only.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .client import AstrBotClient

# Repo-root snapshot written by mcp/scripts/check_openapi_drift.py --update
_SNAPSHOT_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "AstrBot OpenAPI v1.json",
    Path(__file__).resolve().parents[1] / "AstrBot OpenAPI v1.json",
)

_LIVE_CACHE: dict[str, Any] = {"paths": None, "fetched_at": 0.0, "source": None}
_LIVE_CACHE_TTL_S = 300.0

_PARAM_SEG = re.compile(r"\{[^{}]+\}")
_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def normalize_path(path: str) -> str:
    return _PARAM_SEG.sub("{}", path or "")


def parse_core_version(raw: str | None) -> tuple[int, int, int] | None:
    if not raw:
        return None
    m = _VERSION_RE.search(str(raw))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def version_at_least(raw: str | None, minimum: str) -> bool | None:
    """True/False if both parseable; None if either side unknown."""
    cur = parse_core_version(raw)
    need = parse_core_version(minimum)
    if cur is None or need is None:
        return None
    return cur >= need


# ── Feature matrix (public OpenAPI templates) ────────────────────────────
# min_core: documentation hint when path detection is unavailable.
# fallback: what skill MCP / user should use on older cores.
OPENAPI_FEATURES: dict[str, dict[str, Any]] = {
    "install_upload": {
        "path": "/api/v1/plugins/install/upload",
        "methods": ["post"],
        "min_core": "4.16",
        "mutations": True,
        "fallback": None,
        "note": "Scheme A local ZIP upload — skill primary install path",
    },
    "install_url": {
        "path": "/api/v1/plugins/install/url",
        "methods": ["post"],
        "min_core": "4.27",
        "mutations": True,
        "fallback": "astrbot_plugin_install_path",
        "note": "Install from remote package URL (OpenAPI PluginUrlInstallRequest: url required)",
    },
    "install_git": {
        "path": "/api/v1/plugins/install/git",
        "methods": ["post"],
        "min_core": "4.27",
        "mutations": True,
        "fallback": "astrbot_plugin_install_path",
        "note": "Install from git (PluginRepositoryInstallRequest: repository required, ref optional)",
    },
    "install_github": {
        "path": "/api/v1/plugins/install/github",
        "methods": ["post"],
        "min_core": "4.27",
        "mutations": True,
        "fallback": "astrbot_plugin_install_path",
        "note": "Install from GitHub repo shorthand",
    },
    "plugin_update": {
        "path": "/api/v1/plugins/{plugin_id}/update",
        "methods": ["post"],
        "min_core": "4.27",
        "mutations": True,
        "fallback": "astrbot_plugin_install_path",
        "note": "Marketplace/source update for one plugin",
    },
    "plugin_update_all": {
        "path": "/api/v1/plugins/update",
        "methods": ["post"],
        "min_core": "4.27",
        "mutations": True,
        "fallback": "manual per-plugin update / install_path",
        "note": "Bulk plugin update",
    },
    "plugin_changelog": {
        "path": "/api/v1/plugins/{plugin_id}/changelog",
        "methods": ["get"],
        "min_core": "4.27",
        "mutations": False,
        "fallback": "README / GitHub release notes",
        "note": "Per-plugin changelog",
    },
    "plugins_market_changelog": {
        "path": "/api/v1/plugins/changelog",
        "methods": ["get"],
        "min_core": "4.27",
        "mutations": False,
        "fallback": None,
        "note": "Market changelog aggregate",
    },
    "validate_repo": {
        "path": "/api/v1/plugins/validate/repo",
        "methods": ["post"],
        "min_core": "4.27",
        "mutations": False,
        "fallback": "manual metadata review",
        "note": "Validate repo (PluginValidateRepoRequest: repository|url)",
    },
    "log_level": {
        "path": "/api/v1/plugins/{plugin_id}/log-level",
        "methods": ["get", "put"],
        "min_core": "4.27",
        "mutations": False,
        "fallback": "global log level only",
        "note": "Per-plugin log level (public OpenAPI since 4.27)",
    },
    "version_support_check": {
        "path": "/api/v1/plugins/version-support/check",
        "methods": ["post"],
        "min_core": "4.27",
        "mutations": False,
        "fallback": "assume skill floor >=4.27 for generated plugins",
        "note": "Official astrbot_version gate probe",
    },
    "plugin_extensions": {
        "path": "/api/v1/plugins/extensions/{plugin_path}",
        "methods": ["get", "post", "put", "patch", "delete"],
        "min_core": "4.16",
        "mutations": False,
        "fallback": None,
        "note": "Plugin register_web_api extension routes (log bridge SSE)",
    },
}


def _load_snapshot_paths() -> set[str]:
    for cand in _SNAPSHOT_CANDIDATES:
        try:
            if not cand.is_file():
                continue
            spec = json.loads(cand.read_text(encoding="utf-8"))
            paths = spec.get("paths") or {}
            return {normalize_path(p) for p in paths}
        except Exception:  # noqa: BLE001 — snapshot is optional
            continue
    return set()


def fetch_live_openapi_paths(client: AstrBotClient, force: bool = False) -> set[str] | None:
    """Best-effort live OpenAPI path set from the AstrBot host (may 404)."""
    now = time.time()
    if (
        not force
        and _LIVE_CACHE["paths"] is not None
        and (now - float(_LIVE_CACHE["fetched_at"])) < _LIVE_CACHE_TTL_S
    ):
        return set(_LIVE_CACHE["paths"])  # type: ignore[arg-type]

    # Many AstrBot deployments do not serve openapi.json on the LAN port.
    result = client.get("/openapi.json", timeout=8.0)
    paths: set[str] | None = None
    if result.ok and isinstance(result.data, dict) and isinstance(result.data.get("paths"), dict):
        paths = {normalize_path(p) for p in result.data["paths"]}
    else:
        # Try docs host style path sometimes mounted by reverse proxies
        result2 = client.get("/api/openapi.json", timeout=5.0)
        if (
            result2.ok
            and isinstance(result2.data, dict)
            and isinstance(result2.data.get("paths"), dict)
        ):
            paths = {normalize_path(p) for p in result2.data["paths"]}

    if paths is not None:
        _LIVE_CACHE["paths"] = paths
        _LIVE_CACHE["fetched_at"] = now
        _LIVE_CACHE["source"] = "live"
        return set(paths)
    return None


def resolve_running_version(client: AstrBotClient) -> str | None:
    """Use version-support/check side-channel to read running core version."""
    try:
        res = client.post(
            "/api/v1/plugins/version-support/check",
            json_body={"astrbot_version": ">=999999"},
        )
        # message often: "AstrBot X.Y.Z does not satisfy ..."
        text = json.dumps(res.data, ensure_ascii=False) if res.data is not None else ""
        if res.error:
            text = f"{text} {res.error}"
        m = re.search(r"AstrBot (\S+) does not satisfy", text)
        if m:
            return m.group(1)
        # Some cores embed version in data.message / data
        if isinstance(res.data, dict):
            msg = str(res.data.get("message") or res.data.get("data") or "")
            m2 = re.search(r"AstrBot (\S+) does not satisfy", msg)
            if m2:
                return m2.group(1)
    except Exception:  # noqa: BLE001
        return None
    return None


def feature_status(
    feature_id: str,
    *,
    client: AstrBotClient | None = None,
    running_version: str | None = None,
    use_live: bool = True,
) -> dict[str, Any]:
    """
    Return capability report for one feature (never raises).

    Degradation priority (compat with older cores):
      1. Live OpenAPI **successfully fetched** and path absent → unsupported
         (instance truth beats the docs snapshot).
      2. Running core version < min_core → unsupported (core_version_too_old),
         even if the local snapshot lists the path (snapshot ≠ instance).
      3. Live has path, or version>=min_core (optionally + snapshot) → supported.
      4. No evidence → unknown (tools may still attempt; 404 → openapi_unsupported).
    """
    meta = OPENAPI_FEATURES.get(feature_id)
    if not meta:
        return {
            "feature": feature_id,
            "status": "unknown",
            "error_kind": "unknown_feature",
            "known_features": sorted(OPENAPI_FEATURES),
        }

    path = str(meta["path"])
    norm = normalize_path(path)
    min_core = str(meta["min_core"])
    evidence: list[str] = []
    live_fetched = False
    live_has = False
    snapshot_has = False

    live: set[str] | None = None
    if client is not None and use_live:
        live = fetch_live_openapi_paths(client)
        if live is not None:
            live_fetched = True
            if norm in live:
                live_has = True
                evidence.append("live_openapi")
            else:
                evidence.append("live_openapi_absent")

    snap = _load_snapshot_paths()
    if snap:
        if norm in snap:
            snapshot_has = True
            evidence.append("snapshot_openapi")
        else:
            evidence.append("snapshot_openapi_absent")

    ge = version_at_least(running_version, min_core)
    version_ok = ge is True
    version_old = ge is False

    base = {
        "feature": feature_id,
        "path": path,
        "methods": meta["methods"],
        "min_core": min_core,
        "running_version": running_version,
        "evidence": evidence,
        "fallback": meta.get("fallback"),
        "note": meta.get("note"),
    }

    # 1) Instance OpenAPI is authoritative when fetch succeeded
    if live_fetched and not live_has:
        return {
            **base,
            "status": "unsupported",
            "error_kind": "openapi_unsupported",
            "degraded": True,
            "hint": (
                f"Live OpenAPI on this instance has no {path}. "
                f"Fallback: {meta.get('fallback') or 'upgrade AstrBot / use install_path'}."
            ),
        }

    if live_has:
        return {
            **base,
            "status": "supported",
            "hint": "Confirmed in live OpenAPI",
        }

    # 2) Version gate — docs snapshot must NOT make old cores look capable
    if version_old:
        return {
            **base,
            "status": "unsupported",
            "error_kind": "core_version_too_old",
            "degraded": True,
            "hint": (
                f"Running {running_version} < min_core {min_core}. "
                f"Snapshot/docs may list {path} but this instance likely lacks it. "
                f"Fallback: {meta.get('fallback') or 'upgrade AstrBot'}."
            ),
        }

    # 3) Version OK → treat as supported (attempt allowed)
    if version_ok:
        if snapshot_has:
            evidence.append("version_ok+snapshot")
            hint = "Core >= min_core and snapshot lists endpoint"
        else:
            evidence.append("version_hint")
            hint = (
                "Core >= min_core; endpoint not in cached OpenAPI — "
                "attempt allowed; 404 will degrade explicitly"
            )
        return {**base, "status": "supported", "evidence": evidence, "hint": hint}

    # 4) Unknown version: snapshot presence is weak evidence only
    if snapshot_has:
        return {
            **base,
            "status": "unknown",
            "error_kind": "capability_unknown",
            "degraded": True,
            "hint": (
                "Snapshot lists path but running version unknown — "
                "call may 404 on older cores; check astrbot_openapi_capabilities"
            ),
        }

    return {
        **base,
        "status": "unknown",
        "error_kind": "capability_unknown",
        "degraded": True,
        "hint": (
            "No OpenAPI/version evidence; call may 404. "
            f"Fallback: {meta.get('fallback') or 'install_path / upgrade core'}."
        ),
    }


def classify_http_as_capability(
    feature_id: str,
    status_code: int | None,
    *,
    running_version: str | None = None,
) -> dict[str, Any]:
    """Map 404/405/501 on optional endpoints to a degraded capability error."""
    meta = OPENAPI_FEATURES.get(feature_id, {})
    path = meta.get("path")
    if status_code in (404, 405, 501):
        return {
            "ok": False,
            "degraded": True,
            "error_kind": "openapi_unsupported",
            "feature": feature_id,
            "path": path,
            "status_code": status_code,
            "min_core": meta.get("min_core"),
            "running_version": running_version,
            "fallback": meta.get("fallback"),
            "hint": (
                f"Endpoint {path} not available on this AstrBot "
                f"(HTTP {status_code}). Fallback: "
                f"{meta.get('fallback') or 'upgrade core or use Scheme A install_path'}."
            ),
        }
    return {
        "ok": False,
        "error_kind": "http_status",
        "feature": feature_id,
        "status_code": status_code,
        "hint": "Non-capability HTTP error — check auth/body/path",
    }


def capabilities_report(
    client: AstrBotClient | None = None,
    running_version: str | None = None,
    *,
    use_live: bool = True,
) -> dict[str, Any]:
    if client is not None and running_version is None:
        running_version = resolve_running_version(client)
    live_source = _LIVE_CACHE.get("source")
    features = {
        fid: feature_status(
            fid,
            client=client,
            running_version=running_version,
            use_live=use_live,
        )
        for fid in sorted(OPENAPI_FEATURES)
    }
    return {
        "ok": True,
        "running_version": running_version,
        "openapi_source": live_source or ("snapshot" if _load_snapshot_paths() else "none"),
        "snapshot_path_count": len(_load_snapshot_paths()),
        "degradation_policy": (
            "If a feature is unsupported/unknown on older cores, tools return "
            "error_kind=openapi_unsupported|core_version_too_old with fallback_* "
            "instead of retrying blindly. install_path remains the portable path."
        ),
        "features": features,
    }
