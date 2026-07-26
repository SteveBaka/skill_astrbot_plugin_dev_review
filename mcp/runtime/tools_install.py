# [RUNTIME P2] Scheme A: local dir → gitignore ZIP → install/upload → enable/reload/failed.
"""
Primary local-dev install path (LAN multi-device):

  edit on machine A
    → pack ZIP (exclude via .gitignore + hard denylist)
    → POST /api/v1/plugins/install/upload
    → set_enabled(true) [optional]
    → reload
    → plugin_failed probe

ZIP layout matches marketplace / GitHub source packages:
  <plugin_folder>/metadata.yaml
  <plugin_folder>/main.py
  ...

Safety:
  - Requires ASTRBOT_ALLOW_MUTATIONS
  - Prefer update-in-place: re-upload (install_path) without uninstall
  - Same-name conflict: fallback only — uninstall keep config/data then re-upload
  - Prefer testing against astrbot_plugin_mimo_tts only when user allows
  - Never logs token; ZIP bytes not returned to agent (size/stats only)
  - Multipart filename from metadata.yaml name(+version), not raw folder only
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .client import AstrBotClient, encode_plugin_id
from .config import load_config, mutation_denied_payload
from .zip_pack import pack_plugin_directory


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


# [RUNTIME] Agent-facing hint when upload hits same-name / already-installed conflict.
SAME_NAME_CONFLICT_HINT = (
    "Same-name conflict: prefer re-running install_path / reload first. "
    "If upload still fails because the plugin is already installed, fallback: "
    "uninstall with keep_config=true and keep_data=true "
    "(delete_config=false, delete_data=false; never wipe config/data by default), "
    "then install_path again. Do not delete config/data unless the user explicitly asks."
)


def _looks_like_same_name_conflict(upload_ok: bool, upload_data: Any, error: Optional[str]) -> bool:
    """Heuristic: HTTP error body mentions already installed / exists / conflict / 同名."""
    if upload_ok:
        return False
    blob = ""
    if error:
        blob += str(error)
    if upload_data is not None:
        try:
            blob += " " + json.dumps(upload_data, ensure_ascii=False)
        except Exception:
            blob += " " + str(upload_data)
    low = blob.lower()
    keys = (
        "already",
        "exist",
        "conflict",
        "duplicate",
        "installed",
        "同名",
        "已安装",
        "已存在",
        "冲突",
    )
    return any(k in low or k in blob for k in keys)


def _plugin_still_failed(failed_payload: Any, plugin_id: str) -> bool:
    if not isinstance(failed_payload, dict):
        return False
    inner = failed_payload.get("data", failed_payload)
    if isinstance(inner, dict) and plugin_id in inner:
        return True
    if isinstance(inner, list):
        for item in inner:
            if isinstance(item, dict) and (
                item.get("name") == plugin_id or item.get("plugin_id") == plugin_id
            ):
                return True
    return False


def astrbot_plugin_install_path(
    path: str,
    *,
    enable: bool = True,
    reload: bool = True,
    ignore_version_check: bool = False,
) -> str:
    """
    Pack local plugin directory and install via OpenAPI upload.

    path: absolute or ~ path to plugin root (must contain metadata.yaml + main.py)
    enable: PATCH enabled=true after install (default true)
    reload: POST reload after install (default true) — main update loop
    ignore_version_check: reserved / future form field if API accepts extra fields
    """
    cfg = load_config()
    if not cfg.allow_mutations:
        return _dumps(mutation_denied_payload("plugin_install_path"))

    raw_path = (path or "").strip()
    if not raw_path:
        return _dumps(
            {
                "ok": False,
                "error": "path is required (local plugin directory)",
                "error_kind": "bad_request",
            }
        )

    pack = pack_plugin_directory(raw_path)
    if not pack.ok:
        return _dumps(
            {
                "ok": False,
                "error": pack.error,
                "error_kind": pack.error_kind or "pack_failed",
                "path": raw_path,
                "pack": {
                    "gitignore_files": pack.gitignore_files,
                    "pathspec_engine": pack.pathspec_engine,
                    "excluded_sample": pack.excluded_sample,
                },
            }
        )

    plugin_dir = Path(raw_path).expanduser().resolve()
    # Prefer metadata name (used for zip filename + plugin_id guess)
    guessed_id = pack.metadata_name or pack.root_name
    # Multipart filename from metadata.yaml (name-version.zip)
    zip_name = pack.zip_filename or f"{pack.root_name}.zip"

    client = AstrBotClient(cfg)
    # OpenAPI: multipart field name "file"
    upload = client.post_multipart(
        "/api/v1/plugins/install/upload",
        files={
            "file": (zip_name, pack.zip_bytes, "application/zip"),
        },
        # Some builds accept extra form fields; harmless if ignored
        data={"ignore_version_check": "true"} if ignore_version_check else None,
    )

    out: Dict[str, Any] = {
        "ok": upload.ok,
        "mutation": "install_upload",
        "scheme": "A_local_zip_upload",
        "path": str(plugin_dir),
        "guessed_plugin_id": guessed_id,
        "zip_filename": zip_name,
        "pack": {
            "root_name": pack.root_name,
            "zip_filename": zip_name,
            "metadata_name": pack.metadata_name,
            "metadata_version": pack.metadata_version,
            "file_count": pack.file_count,
            "zip_bytes_size": pack.zip_bytes_size,
            "total_bytes_uncompressed": pack.total_bytes_uncompressed,
            "pathspec_engine": pack.pathspec_engine,
            "gitignore_files": pack.gitignore_files,
            "included_sample": pack.included_sample,
            "excluded_sample": pack.excluded_sample,
        },
        "upload": upload.to_dict(),
        "update_policy": {
            "preferred": "re-upload via install_path then reload (no uninstall)",
            "fallback_same_name_conflict": (
                "uninstall keep_config/keep_data true, then install_path again"
            ),
        },
    }

    if not upload.ok:
        conflict = _looks_like_same_name_conflict(upload.ok, upload.data, upload.error)
        out["same_name_conflict_suspected"] = conflict
        out["next_step"] = (
            "Fix upload error_kind (auth/timeout/http_status). "
            "Verify ZIP structure: top-level folder + metadata.yaml + main.py."
        )
        if conflict:
            out["next_step"] = SAME_NAME_CONFLICT_HINT
            out["fallback"] = {
                "1": "Confirm with user if uninstall is acceptable",
                "2": (
                    "astrbot_plugin_uninstall(plugin_id, confirm_uninstall=true, "
                    "keep_config=true, keep_data=true)"
                ),
                "3": "astrbot_plugin_install_path(path) again",
                "note": "Primary path remains re-upload without uninstall when API allows",
            }
        return _dumps(out)

    # Prefer id from response if present
    plugin_id = guessed_id
    if isinstance(upload.data, dict):
        data = upload.data.get("data", upload.data)
        if isinstance(data, dict):
            plugin_id = (
                data.get("name")
                or data.get("plugin_id")
                or data.get("id")
                or plugin_id
            )
        elif isinstance(data, str) and data.strip():
            plugin_id = data.strip()

    out["plugin_id"] = plugin_id
    steps: Dict[str, Any] = {}

    if enable and plugin_id:
        en = client.patch(
            f"/api/v1/plugins/{encode_plugin_id(plugin_id)}/enabled",
            json_body={"enabled": True},
        )
        steps["set_enabled"] = en.to_dict()

    if reload and plugin_id:
        rel = client.post(f"/api/v1/plugins/{encode_plugin_id(plugin_id)}/reload")
        steps["reload"] = rel.to_dict()
        if rel.ok:
            failed = client.get("/api/v1/plugins/failed")
            steps["failed_probe"] = failed.to_dict()
            steps["plugin_in_failed"] = _plugin_still_failed(failed.data, plugin_id)
        else:
            # try failed-endpoint reload once
            rel2 = client.post(
                f"/api/v1/plugins/failed/{encode_plugin_id(plugin_id)}/reload"
            )
            steps["reload_failed_endpoint"] = rel2.to_dict()
            failed = client.get("/api/v1/plugins/failed")
            steps["failed_probe"] = failed.to_dict()
            steps["plugin_in_failed"] = _plugin_still_failed(failed.data, plugin_id)

    if plugin_id:
        got = client.get(f"/api/v1/plugins/{encode_plugin_id(plugin_id)}")
        steps["plugin_get"] = {
            "ok": got.ok,
            "status_code": got.status_code,
            "error": got.error,
            "error_kind": got.error_kind,
        }
        if got.ok and isinstance(got.data, dict):
            g = got.data.get("data") or {}
            if isinstance(g, dict):
                steps["plugin_get_summary"] = {
                    "name": g.get("name"),
                    "version": g.get("version"),
                    "activated": g.get("activated"),
                    "root_dir_name": g.get("root_dir_name"),
                }

    out["post_install"] = steps
    in_failed = bool(steps.get("plugin_in_failed"))
    out["success"] = bool(upload.ok and not in_failed)
    # [RUNTIME P2.5] Privacy-safe Dashboard checklist only (no config reads)
    try:
        from .tools_profile import post_install_dashboard_hints

        out["dashboard_hints"] = post_install_dashboard_hints(str(plugin_id or guessed_id))
    except Exception as exc:  # noqa: BLE001 — install success must not fail on hints
        out["dashboard_hints"] = {"ok": False, "error": repr(exc)}
    if in_failed:
        out["next_step"] = (
            "Install uploaded but plugin is in failed list — fix load error, "
            "then astrbot_plugin_reload(failed=true) or re-upload."
        )
    else:
        out["next_step"] = (
            "OK. Configure in Dashboard if needed (see dashboard_hints). "
            "Ensure profile plugin_dev_skill (astrbot_ensure_plugin_dev_skill). "
            "User tests in WebChat; Agent does not auto chat_probe. "
            "Dev loop: edit → install_path again."
        )
    return _dumps(out)


def astrbot_plugin_pack_preview(path: str) -> str:
    """
    Dry-run: build ZIP stats without uploading (no mutations required).

    Use to verify .gitignore exclusions before install.
    """
    pack = pack_plugin_directory((path or "").strip())
    return _dumps(
        {
            "ok": pack.ok,
            "error": pack.error,
            "error_kind": pack.error_kind,
            "path": path,
            "root_name": pack.root_name,
            "zip_filename": pack.zip_filename,
            "metadata_name": pack.metadata_name,
            "metadata_version": pack.metadata_version,
            "file_count": pack.file_count,
            "zip_bytes_size": pack.zip_bytes_size,
            "total_bytes_uncompressed": pack.total_bytes_uncompressed,
            "pathspec_engine": pack.pathspec_engine,
            "gitignore_files": pack.gitignore_files,
            "included_sample": pack.included_sample,
            "excluded_sample": pack.excluded_sample,
            "note": "No OpenAPI call. Use astrbot_plugin_install_path to upload.",
            "zip_name_rule": "{metadata.name}-{metadata.version}.zip (fallback name or folder)",
        }
    )
