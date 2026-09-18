# [RUNTIME P2+] Newer OpenAPI plugin capabilities with graceful degradation.
"""
Wrappers around AstrBot OpenAPI endpoints that are newer than the skill's
portable Scheme A path (install/upload). Every call:

  1. Gates mutations via load_config().allow_mutations (mutation_denied_payload)
  2. Requires confirm=true for write tools
  3. Resolves capability (openapi_caps.feature_status)
  4. If unsupported / version too old → structured degraded payload
  5. HTTP 404/405/501 on optional paths → openapi_unsupported + fallback

Portable baseline always remains:
  astrbot_plugin_pack_preview + astrbot_plugin_install_path
"""

from __future__ import annotations

import json
from typing import Any

from .client import AstrBotClient
from .config import load_config, mutation_denied_payload
from .openapi_caps import (
    capabilities_report,
    classify_http_as_capability,
    feature_status,
    resolve_running_version,
)


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _client() -> tuple[AstrBotClient, Any]:
    cfg = load_config()
    return AstrBotClient(cfg), cfg


def _gate(action: str) -> str | None:
    """Return dumps(mutation_denied) if mutations off; else None."""
    _c, cfg = _client()
    if not cfg.allow_mutations:
        return _dumps(mutation_denied_payload(action))
    return None


def _confirm_required(action: str, extra: dict[str, Any] | None = None) -> str:
    payload = {
        "ok": False,
        "error_kind": "confirm_required",
        "action": action,
        "hint": (
            f"{action} mutates the AstrBot instance. Set confirm=true only after "
            "explicit user approval."
        ),
    }
    if extra:
        payload.update(extra)
    return _dumps(payload)


def astrbot_openapi_capabilities(use_live: bool = True) -> str:
    """Report which newer OpenAPI plugin features the instance supports."""
    client, cfg = _client()
    if not cfg.enabled:
        return _dumps(
            {
                "ok": False,
                "error_kind": "not_configured",
                "hint": "Set ASTRBOT_BASE_URL (+ token) on the MCP host.",
                "features_expected": True,
            }
        )
    return _dumps(capabilities_report(client, use_live=use_live))


def _degraded_payload(feature_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    client, _cfg = _client()
    running = resolve_running_version(client)
    st = feature_status(feature_id, client=client, running_version=running, use_live=True)
    payload = {
        "ok": False,
        "degraded": True,
        "error_kind": st.get("error_kind") or "openapi_unsupported",
        "capability": st,
        "fallback": st.get("fallback"),
        "portable_tool": "astrbot_plugin_install_path",
    }
    if extra:
        payload.update(extra)
    return payload


def _http_fail(
    feature_id: str, res: Any, running: str | None, extra: dict[str, Any]
) -> dict[str, Any]:
    cap = classify_http_as_capability(feature_id, res.status_code, running_version=running)
    if cap.get("error_kind") == "openapi_unsupported":
        return {**cap, **extra, "http_error": res.error}
    return {
        "ok": False,
        "error_kind": res.error_kind or "http_status",
        "status_code": res.status_code,
        "error": res.error,
        **extra,
    }


def astrbot_plugin_install_url(
    url: str,
    enable: bool = True,
    reload: bool = True,
    confirm: bool = False,
) -> str:
    """
    [RUNTIME P2+] POST /plugins/install/url — install from remote package URL.

    Degradable when core lacks endpoint. Needs ASTRBOT_ALLOW_MUTATIONS + confirm=true.
    """
    if not url or not str(url).strip().lower().startswith(("http://", "https://")):
        return _dumps(
            {
                "ok": False,
                "error_kind": "invalid_url",
                "hint": "url must be http(s)://… package URL",
            }
        )
    denied = _gate("astrbot_plugin_install_url")
    if denied:
        return denied
    if not confirm:
        return _confirm_required("astrbot_plugin_install_url", {"url_preview": str(url)[:80]})

    client, _cfg = _client()
    running = resolve_running_version(client)
    st = feature_status("install_url", client=client, running_version=running, use_live=True)
    if st.get("status") == "unsupported" and st.get("error_kind") == "core_version_too_old":
        return _dumps(_degraded_payload("install_url", {"requested_url": str(url)[:120]}))

    # PluginUrlInstallRequest: required url
    last: Any = None
    body = {"url": str(url).strip()}
    last = client.post("/api/v1/plugins/install/url", json_body=body)
    res = last
    if not res.ok:
        return _dumps(
            _http_fail(
                "install_url",
                res,
                running,
                {
                    "requested_url": str(url)[:120],
                    "portable_tool": "astrbot_plugin_install_path",
                    "capability": st,
                },
            )
        )

    post: dict[str, Any] = {}
    if enable:
        name = None
        data = res.data
        if isinstance(data, dict):
            inner = data.get("data") if isinstance(data.get("data"), dict) else data
            name = inner.get("name") or inner.get("plugin_id")
        if name:
            en = client.patch(f"/api/v1/plugins/{name}/enabled", json_body={"enabled": True})
            post["set_enabled"] = en.to_dict()
            if reload:
                post["reload"] = client.post(f"/api/v1/plugins/{name}/reload").to_dict()
    return _dumps(
        {
            "ok": True,
            "feature": "install_url",
            "status_code": res.status_code,
            "data": res.data,
            "running_version": running,
            "capability": st,
            "post_install": post,
            "hint": "Remote install succeeded. Prefer install_path for local dev loops.",
        }
    )


def astrbot_plugin_install_git(
    url: str,
    ref: str = "",
    enable: bool = True,
    reload: bool = True,
    confirm: bool = False,
) -> str:
    """[RUNTIME P2+] POST /plugins/install/git — install from git remote (degradable)."""
    denied = _gate("astrbot_plugin_install_git")
    if denied:
        return denied
    if not confirm:
        return _confirm_required("astrbot_plugin_install_git")

    client, _cfg = _client()
    running = resolve_running_version(client)
    st = feature_status("install_git", client=client, running_version=running, use_live=True)
    if st.get("status") == "unsupported" and st.get("error_kind") == "core_version_too_old":
        return _dumps(_degraded_payload("install_git", {"requested_url": str(url)[:120]}))

    # PluginRepositoryInstallRequest: required repository (+ optional ref)
    body: dict[str, Any] = {"repository": str(url).strip()}
    if ref:
        body["ref"] = ref
    res = client.post("/api/v1/plugins/install/git", json_body=body)
    if not res.ok:
        return _dumps(
            _http_fail(
                "install_git",
                res,
                running,
                {"requested_url": str(url)[:120], "capability": st},
            )
        )
    return _dumps(
        {
            "ok": True,
            "feature": "install_git",
            "data": res.data,
            "running_version": running,
            "capability": st,
            "post_hint": "enable/reload via astrbot_plugin_set_enabled / reload if needed",
            "enable": enable,
            "reload": reload,
        }
    )


def astrbot_plugin_update(plugin_id: str, confirm: bool = False) -> str:
    """
    [RUNTIME P2+] POST /plugins/{plugin_id}/update — marketplace/source update.

    Degrades to install_path when endpoint missing.
    """
    denied = _gate("astrbot_plugin_update")
    if denied:
        return denied
    if not confirm:
        return _confirm_required("astrbot_plugin_update", {"plugin_id": plugin_id})

    client, _cfg = _client()
    running = resolve_running_version(client)
    st = feature_status("plugin_update", client=client, running_version=running, use_live=True)
    if st.get("status") == "unsupported" and st.get("error_kind") == "core_version_too_old":
        return _dumps(
            _degraded_payload(
                "plugin_update",
                {
                    "plugin_id": plugin_id,
                    "fallback_tool": "astrbot_plugin_install_path",
                    "hint": (
                        "Re-upload local source via install_path "
                        "(bump version / force_refresh=true)."
                    ),
                },
            )
        )

    pid = str(plugin_id).strip()
    # PluginUpdateRequest: optional reinstall flag
    res = client.post(f"/api/v1/plugins/{pid}/update", json_body={"reinstall": False})
    if not res.ok:
        return _dumps(
            _http_fail(
                "plugin_update",
                res,
                running,
                {
                    "plugin_id": pid,
                    "fallback_tool": "astrbot_plugin_install_path",
                    "capability": st,
                    "hint": (
                        "If core lacks update API use Scheme A install_path "
                        "(bump metadata.version or force_refresh=true)."
                    ),
                },
            )
        )

    failed = client.get("/api/v1/plugins/failed")
    return _dumps(
        {
            "ok": True,
            "feature": "plugin_update",
            "plugin_id": pid,
            "data": res.data,
            "running_version": running,
            "capability": st,
            "failed_probe": failed.to_dict(),
        }
    )


def astrbot_plugin_changelog(plugin_id: str = "") -> str:
    """[RUNTIME P2+] GET plugin changelog (per-plugin or market aggregate). Degradable."""
    client, _cfg = _client()
    running = resolve_running_version(client)
    fid = "plugin_changelog" if plugin_id else "plugins_market_changelog"
    st = feature_status(fid, client=client, running_version=running, use_live=True)
    if st.get("status") == "unsupported" and st.get("error_kind") == "core_version_too_old":
        return _dumps(
            _degraded_payload(
                fid,
                {"plugin_id": plugin_id or None, "hint": "Use README / GitHub releases."},
            )
        )

    if plugin_id:
        pid = str(plugin_id).strip()
        res = client.get(f"/api/v1/plugins/{pid}/changelog")
    else:
        pid = ""
        res = client.get("/api/v1/plugins/changelog")

    if not res.ok:
        return _dumps(
            _http_fail(
                fid,
                res,
                running,
                {
                    "plugin_id": pid or None,
                    "capability": st,
                    "hint": "Changelog API unavailable — read plugin README or market page.",
                },
            )
        )
    return _dumps(
        {
            "ok": True,
            "feature": fid,
            "plugin_id": pid or None,
            "data": res.data,
            "running_version": running,
            "capability": st,
        }
    )


def astrbot_plugin_validate_repo(repo: str) -> str:
    """[RUNTIME P2+] POST /plugins/validate/repo — read-only repo validation. Degradable."""
    client, _cfg = _client()
    running = resolve_running_version(client)
    st = feature_status("validate_repo", client=client, running_version=running, use_live=True)
    if st.get("status") == "unsupported" and st.get("error_kind") == "core_version_too_old":
        return _dumps(
            _degraded_payload(
                "validate_repo",
                {
                    "repo": str(repo)[:120],
                    "hint": "Manually check metadata.yaml + astrbot_version.",
                },
            )
        )
    repo_val = str(repo).strip()
    # PluginValidateRepoRequest: repository | url (+ proxy)
    last: Any = None
    for key in ("repository", "url"):
        last = client.post("/api/v1/plugins/validate/repo", json_body={key: repo_val})
        if last.ok or last.status_code in (404, 405, 501):
            break
    res = last
    if not res.ok:
        msg = None
        if isinstance(res.data, dict):
            msg = res.data.get("message")
        return _dumps(
            _http_fail(
                "validate_repo",
                res,
                running,
                {
                    "repo": repo_val[:120],
                    "capability": st,
                    "last_http_message": msg,
                    "hint": "Endpoint reachable but body schema may differ — check OpenAPI schema.",
                },
            )
        )
    return _dumps(
        {
            "ok": True,
            "feature": "validate_repo",
            "repo": repo_val[:200],
            "data": res.data,
            "running_version": running,
            "capability": st,
        }
    )
