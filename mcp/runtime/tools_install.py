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

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from .client import AstrBotClient, encode_plugin_id
from .config import load_config, mutation_denied_payload
from .zip_pack import pack_plugin_directory


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _main_py_hash_from_zip(zip_bytes: bytes) -> str | None:
    """Short fingerprint of main.py inside the packed ZIP (content identity)."""
    try:
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            mains = [
                n
                for n in zf.namelist()
                if n.replace("\\", "/").endswith("/main.py") or n.replace("\\", "/") == "main.py"
            ]
            if not mains:
                return None
            # Prefer shallowest main.py (plugin root)
            mains.sort(key=lambda n: n.count("/"))
            return _sha256_hex(zf.read(mains[0]))[:16]
    except Exception:
        return None


def _components_fingerprint(components: Any) -> list[dict[str, str]]:
    """Stable, non-secret snapshot of plugin components for stale-install detection."""
    out: list[dict[str, str]] = []
    if not isinstance(components, list):
        return out
    for c in components:
        if not isinstance(c, dict):
            continue
        out.append(
            {
                "type": str(c.get("type") or ""),
                "name": str(c.get("name") or c.get("command") or ""),
                "command": str(c.get("command") or ""),
                # description often carries handler docstring — best signal we have
                "description": str(c.get("description") or "")[:160],
            }
        )
    out.sort(key=lambda x: (x["type"], x["command"], x["name"]))
    return out


def _plugin_get_snapshot(client: AstrBotClient, plugin_id: str) -> dict[str, Any]:
    got = client.get(f"/api/v1/plugins/{encode_plugin_id(plugin_id)}")
    snap: dict[str, Any] = {
        "ok": got.ok,
        "status_code": got.status_code,
        "error": got.error,
        "error_kind": got.error_kind,
        "present": False,
    }
    if got.ok and isinstance(got.data, dict):
        g = got.data.get("data") or {}
        if isinstance(g, dict) and g:
            snap["present"] = True
            snap["name"] = g.get("name")
            snap["version"] = g.get("version")
            snap["activated"] = g.get("activated")
            snap["root_dir_name"] = g.get("root_dir_name")
            snap["components"] = _components_fingerprint(g.get("components"))
            snap["components_count"] = len(snap["components"])
    return snap


def _components_look_unchanged(before: dict[str, Any] | None, after: dict[str, Any] | None) -> bool:
    """True when both snapshots exist and component fingerprints are identical."""
    if not before or not after:
        return False
    if not before.get("present") or not after.get("present"):
        return False
    b = before.get("components")
    a = after.get("components")
    if not isinstance(b, list) or not isinstance(a, list):
        return False
    # Empty both: weak signal, treat as unchanged only if versions also equal
    if not b and not a:
        return str(before.get("version") or "") == str(after.get("version") or "")
    return b == a


def _install_fingerprint_compare(
    before_snap: dict[str, Any] | None,
    after_snap: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Structured before/after install fingerprint (plan B: version as evidence).

    Includes:
      - version (primary positive signal when bump succeeded)
      - component metadata fingerprint (type/name/command/description)
    Does NOT invent on-disk main.py hashes (OpenAPI does not expose them).
    """
    before_snap = before_snap or {}
    after_snap = after_snap or {}
    v_before = str(before_snap.get("version") or "")
    v_after = str(after_snap.get("version") or "")
    comps_same = _components_look_unchanged(before_snap, after_snap)
    c_before = before_snap.get("components_count")
    c_after = after_snap.get("components_count")
    delta: list[str] = []
    if v_before != v_after:
        delta.append(f"version {v_before or '?'} -> {v_after or '?'}")
    if not comps_same:
        delta.append("components fingerprint changed")
    elif c_before is not None and c_after is not None and c_before == c_after:
        delta.append("components fingerprint identical")
    return {
        "version_before": v_before,
        "version_after": v_after,
        "version_changed": bool(v_before) and bool(v_after) and v_before != v_after,
        "components_same": comps_same,
        "components_count_before": c_before,
        "components_count_after": c_after,
        "notes": delta,
    }


def _classify_install_staleness(
    before_snap: dict[str, Any] | None,
    after_snap: dict[str, Any] | None,
    *,
    refresh_mode: str,
    pack_main_py_sha256_16: str | None = None,
    last_pack_main_py_sha256_16: str | None = None,
) -> dict[str, Any]:
    """
    Plan A+D: tiered stale-install classification for agent-safe install_path output.

    Decision (upload already succeeded; caller handles failed separately):
      1. version_changed (+ not failed) → install_ok_version_bumped
         — do NOT emit possible_stale_install (avoids false-positive force_refresh).
      2. components_same AND version_same:
         - pack hash known + equals last hash → possible_stale_install / high
         - pack hash changed vs last → pack_changed_components_same / info
         - last hash unknown → possible_stale_install / low (conservative same-version)
      3. else → install_ok (components or metadata moved in a useful way)

    refresh_mode != upload_only (force_refresh reinstall) → prefer install_ok unless
    version+components both unchanged after reinstall (still low confidence stale).
    """
    fp = _install_fingerprint_compare(before_snap, after_snap)
    v_changed = fp["version_changed"]
    comps_same = fp["components_same"]
    present_before = bool((before_snap or {}).get("present"))
    present_after = bool((after_snap or {}).get("present"))

    pack_hash = pack_main_py_sha256_16 or None
    last_hash = last_pack_main_py_sha256_16 or None
    pack_hash_changed = pack_hash is not None and last_hash is not None and pack_hash != last_hash
    pack_hash_same = pack_hash is not None and last_hash is not None and pack_hash == last_hash

    if not present_before or not present_after:
        return {
            "status": "install_ok",
            "possible_stale_install": False,
            "stale_confidence": "none",
            "install_fingerprint": fp,
            "pack_main_py_sha256_16": pack_hash,
            "stale_hint": "",
            "agent_action": "continue",
        }

    # 1) Version bump is the strongest non-stale signal (A + B.version)
    if v_changed and comps_same:
        return {
            "status": "install_ok_version_bumped",
            "possible_stale_install": False,
            "stale_confidence": "none",
            "install_fingerprint": fp,
            "pack_main_py_sha256_16": pack_hash,
            "stale_hint": (
                f"Metadata version changed {fp['version_before']} -> {fp['version_after']}; "
                "component fingerprint is unchanged because command names/docstrings "
                "did not change — this is NORMAL for handler-internal edits. "
                "Do NOT force_refresh solely for this. If you only changed handler "
                "internals, verify behavior with smoke/WebChat."
            ),
            "agent_action": ("treat_as_success; optional smoke if behavior must be proven"),
        }
    if v_changed and not comps_same:
        return {
            "status": "install_ok",
            "possible_stale_install": False,
            "stale_confidence": "none",
            "install_fingerprint": fp,
            "pack_main_py_sha256_16": pack_hash,
            "stale_hint": (
                f"Version bumped ({fp['version_before']} -> {fp['version_after']}) and "
                "component fingerprint changed — install likely replaced code/registration."
            ),
            "agent_action": "continue",
        }

    # 2) Same version + same components → tier by pack hash evidence
    if comps_same and not v_changed:
        if refresh_mode != "upload_only":
            return {
                "status": "install_ok",
                "possible_stale_install": False,
                "stale_confidence": "none",
                "install_fingerprint": fp,
                "pack_main_py_sha256_16": pack_hash,
                "stale_hint": (
                    "force_refresh reinstall completed; component fingerprint unchanged "
                    "with same version is expected when only handler internals changed."
                ),
                "agent_action": "continue; smoke if needed",
            }
        if pack_hash_same:
            return {
                "status": "possible_stale_install",
                "possible_stale_install": True,
                "stale_confidence": "high",
                "install_fingerprint": fp,
                "pack_main_py_sha256_16": pack_hash,
                "last_pack_main_py_sha256_16": last_hash,
                "stale_hint": (
                    "Same metadata.version, identical component fingerprint, AND "
                    "identical main.py pack hash as the previous upload — the package "
                    "content likely did not change. Bump metadata.version or use "
                    "force_refresh=true if you expected new code."
                ),
                "agent_action": ("bump version or force_refresh only if code should have changed"),
            }
        if pack_hash_changed:
            return {
                "status": "pack_changed_components_same",
                "possible_stale_install": False,
                "stale_confidence": "none",
                "install_fingerprint": fp,
                "pack_main_py_sha256_16": pack_hash,
                "last_pack_main_py_sha256_16": last_hash,
                "stale_hint": (
                    "Same version and same command/docstring fingerprint, but packed "
                    "main.py hash differs from the last upload — handler-internal change "
                    "is likely. Prefer smoke/WebChat over force_refresh."
                ),
                "agent_action": "smoke to verify behavior; avoid auto force_refresh",
            }
        # No last-hash baseline (or unknown) — conservative low-confidence stale
        return {
            "status": "possible_stale_install",
            "possible_stale_install": True,
            "stale_confidence": "low",
            "install_fingerprint": fp,
            "pack_main_py_sha256_16": pack_hash,
            "last_pack_main_py_sha256_16": last_hash,
            "stale_hint": (
                "Same metadata.version and identical component fingerprint after "
                "upload_only re-upload. AstrBot does not guarantee same-version file "
                "replacement. Confidence is LOW when pack hash baseline is unknown — "
                "prefer bumping metadata.version or smoke first; use force_refresh=true "
                "only if behavior is still old."
            ),
            "agent_action": ("smoke first; then bump version or force_refresh if behavior stale"),
        }

    # 3) Components changed but version same — treat as successful registration update
    return {
        "status": "install_ok",
        "possible_stale_install": False,
        "stale_confidence": "none",
        "install_fingerprint": fp,
        "pack_main_py_sha256_16": pack_hash,
        "stale_hint": "",
        "agent_action": "continue",
    }


def _uninstall_keep_all(client: AstrBotClient, plugin_id: str) -> dict[str, Any]:
    """
    Uninstall preserving config + data (OpenAPI delete_*=false).

    Used only for force_refresh / same-name recovery — never wipes user data.
    """
    result = client.delete(
        f"/api/v1/plugins/{encode_plugin_id(plugin_id)}",
        json_body={"delete_config": False, "delete_data": False},
    )
    return result.to_dict()


# [RUNTIME] Agent-facing hint when upload hits same-name / already-installed conflict.
SAME_NAME_CONFLICT_HINT = (
    "Same-name conflict: prefer re-running install_path / reload first. "
    "If upload still fails because the plugin is already installed, fallback: "
    "uninstall with keep_config=true and keep_data=true "
    "(delete_config=false, delete_data=false; never wipe config/data by default), "
    "then install_path again. Do not delete config/data unless the user explicitly asks."
)


def _looks_like_same_name_conflict(upload_ok: bool, upload_data: Any, error: str | None) -> bool:
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


def _run_upload_enable_reload(
    client: AstrBotClient,
    *,
    zip_name: str,
    zip_bytes: bytes,
    ignore_version_check: bool,
    enable: bool,
    reload: bool,
    plugin_id_hint: str,
) -> tuple[Any, str, dict[str, Any]]:
    """Upload ZIP then optional enable/reload/failed/get. Returns (upload, plugin_id, steps)."""
    upload = client.post_multipart(
        "/api/v1/plugins/install/upload",
        files={"file": (zip_name, zip_bytes, "application/zip")},
        data={"ignore_version_check": "true"} if ignore_version_check else None,
    )
    plugin_id = plugin_id_hint
    if upload.ok and isinstance(upload.data, dict):
        data = upload.data.get("data", upload.data)
        if isinstance(data, dict):
            plugin_id = data.get("name") or data.get("plugin_id") or data.get("id") or plugin_id
        elif isinstance(data, str) and data.strip():
            plugin_id = data.strip()

    steps: dict[str, Any] = {}
    if not upload.ok:
        return upload, plugin_id, steps

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
            rel2 = client.post(f"/api/v1/plugins/failed/{encode_plugin_id(plugin_id)}/reload")
            steps["reload_failed_endpoint"] = rel2.to_dict()
            failed = client.get("/api/v1/plugins/failed")
            steps["failed_probe"] = failed.to_dict()
            steps["plugin_in_failed"] = _plugin_still_failed(failed.data, plugin_id)

    if plugin_id:
        after = _plugin_get_snapshot(client, plugin_id)
        steps["plugin_get"] = {
            "ok": after.get("ok"),
            "status_code": after.get("status_code"),
            "error": after.get("error"),
            "error_kind": after.get("error_kind"),
        }
        if after.get("present"):
            steps["plugin_get_summary"] = {
                "name": after.get("name"),
                "version": after.get("version"),
                "activated": after.get("activated"),
                "root_dir_name": after.get("root_dir_name"),
                "components_count": after.get("components_count"),
            }
        steps["plugin_snapshot_after"] = after

    return upload, plugin_id, steps


def astrbot_plugin_install_path(
    path: str,
    *,
    enable: bool = True,
    reload: bool = True,
    ignore_version_check: bool = False,
    force_refresh: bool = False,
    clear_failed: bool = False,
) -> str:
    """
    Pack local plugin directory and install via OpenAPI upload.

    path: absolute or ~ path to plugin root (must contain metadata.yaml + main.py)
    enable: PATCH enabled=true after install (default true)
    reload: POST reload after install (default true) — main update loop
    ignore_version_check: reserved / future form field if API accepts extra fields
    force_refresh: if true and plugin already present, uninstall(keep config+data)
        then upload once — use when same-version re-upload leaves stale code.
        Default false: never auto-uninstall.

    Staleness (plan A+D + version evidence):
      install_status in {install_ok, install_ok_version_bumped, pack_changed_components_same,
      possible_stale_install}. possible_stale_install is NOT set when metadata.version
      changed after upload (avoids false-positive force_refresh). When version is unchanged
      and component fingerprint is identical, stale_confidence is low|high (high only if
      packed main.py hash matches the previous upload baseline).
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
    guessed_id = pack.metadata_name or pack.root_name
    zip_name = pack.zip_filename or f"{pack.root_name}.zip"
    main_hash = _main_py_hash_from_zip(pack.zip_bytes)

    client = AstrBotClient(cfg)
    before_snap = _plugin_get_snapshot(client, guessed_id) if guessed_id else {"present": False}

    # stale-failed detection: plugin NOT in normal list but present in failed list
    # → mutations (upload/enable/reload/uninstall) are typically blocked server-side
    # with generic "插件操作失败"; force_refresh cannot fix it (only failed entry).
    stale_failed: dict[str, Any] | None = None
    if not before_snap.get("present") and guessed_id:
        failed_resp = client.get("/api/v1/plugins/failed")
        if failed_resp.ok and isinstance(failed_resp.data, dict):
            fdata = failed_resp.data.get("data") or {}
            rec = None
            if isinstance(fdata, dict):
                for k, v in fdata.items():
                    if guessed_id in (str(k), str(v.get("name")) if isinstance(v, dict) else ""):
                        rec = v
                        break
            if rec is not None:
                stale_failed = {
                    "detected": True,
                    "plugin_id": guessed_id,
                    "detail": rec if isinstance(rec, dict) else str(rec)[:200],
                    "hint": (
                        "Plugin exists ONLY in the failed list — server-side stale "
                        "failed record blocks all mutations (install/enable/reload/"
                        "uninstall return '插件操作失败，请查看服务端日志'). "
                        "force_refresh cannot clear it. Clean it up in Dashboard "
                        "(or filesystem) first, then re-upload. Do not keep retrying."
                    ),
                }

    refresh_mode = "upload_only"
    pre_uninstall: dict[str, Any] | None = None
    pre_clear_failed: dict[str, Any] | None = None

    # clear_failed: when a stale failed record blocks all mutations, remove it
    # first (keep config/data) then upload. Opt-in — never auto-delete.
    if stale_failed and clear_failed:
        del_res = client.delete(
            f"/api/v1/plugins/failed/{encode_plugin_id(guessed_id)}",
            json_body={"delete_config": False, "delete_data": False},
        )
        pre_clear_failed = del_res.to_dict()
        refresh_mode = "cleared_failed_then_upload"
        if del_res.ok:
            # re-snapshot: plugin should now be absent entirely
            before_snap = _plugin_get_snapshot(client, guessed_id)
        else:
            return _dumps(
                {
                    "ok": False,
                    "error": (
                        "clear_failed requested but DELETE .../plugins/failed/{id} "
                        "failed; upload not attempted."
                    ),
                    "error_kind": "clear_failed_failed",
                    "plugin_id": guessed_id,
                    "pre_clear_failed": pre_clear_failed,
                    "stale_failed": stale_failed,
                }
            )

    # force_refresh: only when already installed — uninstall keep_* then upload.
    # Does NOT handle plugins that only exist in the failed list (see stale_failed).
    if force_refresh and before_snap.get("present") and guessed_id:
        pre_uninstall = _uninstall_keep_all(client, guessed_id)
        refresh_mode = "reinstall_keep_config_data"
        if not pre_uninstall.get("ok"):
            return _dumps(
                {
                    "ok": False,
                    "error": (
                        "force_refresh requested but uninstall(keep config/data) failed; "
                        "upload not attempted."
                    ),
                    "error_kind": "force_refresh_uninstall_failed",
                    "plugin_id": guessed_id,
                    "refresh_mode": refresh_mode,
                    "pre_uninstall": pre_uninstall,
                    "snapshot_before": before_snap,
                    "pack_main_py_sha256_16": main_hash,
                    "hint": (
                        "Check mutations/auth. Uninstall defaults never delete config/data; "
                        "if user wanted wipe, that is a separate explicit uninstall."
                    ),
                }
            )

    upload, plugin_id, steps = _run_upload_enable_reload(
        client,
        zip_name=zip_name,
        zip_bytes=pack.zip_bytes,
        ignore_version_check=ignore_version_check,
        enable=enable,
        reload=reload,
        plugin_id_hint=guessed_id,
    )

    out: dict[str, Any] = {
        "ok": upload.ok,
        "mutation": "install_upload",
        "scheme": "A_local_zip_upload",
        "path": str(plugin_dir),
        "guessed_plugin_id": guessed_id,
        "zip_filename": zip_name,
        "refresh_mode": refresh_mode,
        "force_refresh": bool(force_refresh),
        "clear_failed": bool(clear_failed),
        "stale_failed": stale_failed,
        "pre_clear_failed": pre_clear_failed,
        "pack_main_py_sha256_16": main_hash,
        "snapshot_before": {
            "present": before_snap.get("present"),
            "version": before_snap.get("version"),
            "components_count": before_snap.get("components_count"),
        },
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
            "stale_same_version": (
                "success=true does NOT guarantee on-disk code replaced when "
                "metadata.version is unchanged. Check install_status / "
                "stale_confidence: version bump → install_ok_version_bumped "
                "(no force_refresh needed); same-version + identical components → "
                "possible_stale_install low|high. Prefer smoke, then bump version "
                "or force_refresh=true (keep config/data) only if behavior is old."
            ),
            "fallback_same_name_conflict": (
                "uninstall keep_config/keep_data true, then install_path again"
            ),
        },
    }
    if pre_uninstall is not None:
        out["pre_uninstall"] = pre_uninstall

    if not upload.ok:
        conflict = _looks_like_same_name_conflict(upload.ok, upload.data, upload.error)
        out["same_name_conflict_suspected"] = conflict
        if stale_failed:
            out["next_step"] = (
                "Upload rejected while a STALE FAILED record for this plugin exists "
                "(see stale_failed). Stop retrying: clean the plugin from Dashboard "
                "failed list / filesystem, then re-upload."
            )
        else:
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
                "or": "astrbot_plugin_install_path(path, force_refresh=true)",
                "note": "Primary path remains re-upload without uninstall when API allows",
            }
        return _dumps(out)

    out["plugin_id"] = plugin_id
    out["post_install"] = steps

    after_snap = steps.get("plugin_snapshot_after") or _plugin_get_snapshot(
        client, str(plugin_id or guessed_id)
    )
    out["snapshot_after"] = {
        "present": after_snap.get("present"),
        "version": after_snap.get("version"),
        "components_count": after_snap.get("components_count"),
    }

    # Stale detection (A+D + version evidence): tiered — version bump is not stale.
    pid_key = str(plugin_id or guessed_id)
    last_pack = _LAST_PACK_HASH_BY_PLUGIN.get(pid_key)
    classified = _classify_install_staleness(
        before_snap,
        after_snap,
        refresh_mode=refresh_mode,
        pack_main_py_sha256_16=main_hash,
        last_pack_main_py_sha256_16=last_pack,
    )
    if main_hash:
        _LAST_PACK_HASH_BY_PLUGIN[pid_key] = main_hash

    out["install_status"] = classified["status"]
    out["install_fingerprint"] = classified["install_fingerprint"]
    out["stale_confidence"] = classified["stale_confidence"]
    out["agent_action"] = classified.get("agent_action") or "continue"
    if classified.get("pack_main_py_sha256_16"):
        out["pack_main_py_sha256_16"] = classified["pack_main_py_sha256_16"]
    if classified.get("last_pack_main_py_sha256_16"):
        out["last_pack_main_py_sha256_16"] = classified["last_pack_main_py_sha256_16"]
    if classified.get("stale_hint"):
        out["stale_hint"] = classified["stale_hint"]

    possible_stale = bool(classified.get("possible_stale_install"))
    if possible_stale:
        out["warning"] = "possible_stale_install"
        out["possible_stale_install"] = True
    else:
        out["possible_stale_install"] = False

    in_failed = bool(steps.get("plugin_in_failed"))
    out["success"] = bool(upload.ok and not in_failed)

    if in_failed:
        try:
            from .error_fingerprint import record_diagnoses_if_enabled
            from .failure_analysis import analyze_failed_payload

            failed_payload = steps.get("failed_probe", {}).get("data")
            analysis = analyze_failed_payload(failed_payload)
            mine = [
                d
                for d in analysis["diagnoses"]
                if str(plugin_id or "") in (d.get("dir_name", ""), d.get("plugin_name", ""))
            ]
            out["failure_diagnosis"] = mine or analysis["diagnoses"]
            recorded = record_diagnoses_if_enabled(
                out["failure_diagnosis"], source=f"install:{pid_key}"
            )
            if recorded:
                out["error_kb_recorded"] = recorded
        except Exception as exc:  # noqa: BLE001
            out["failure_diagnosis"] = {"ok": False, "error": repr(exc)}

    try:
        from .tools_profile import post_install_dashboard_hints

        out["dashboard_hints"] = post_install_dashboard_hints(pid_key)
    except Exception as exc:  # noqa: BLE001
        out["dashboard_hints"] = {"ok": False, "error": repr(exc)}

    status = classified["status"]
    v_b = classified["install_fingerprint"].get("version_before") or "?"
    v_a = classified["install_fingerprint"].get("version_after") or "?"
    if in_failed:
        out["next_step"] = (
            "Install uploaded but plugin is in failed list — fix load error, "
            "then astrbot_plugin_reload(failed=true) or re-upload."
        )
    elif status == "install_ok_version_bumped":
        out["next_step"] = (
            f"Install OK — version {v_b} -> {v_a}. Component fingerprint unchanged "
            "is expected when commands/docstrings did not change. "
            "Do NOT force_refresh solely for that. Smoke only if handler-internal "
            "behavior must be proven."
        )
    elif status == "pack_changed_components_same":
        out["next_step"] = (
            "Install OK — packed main.py hash changed with same version/components. "
            "Prefer smoke over force_refresh to confirm handler behavior."
        )
    elif possible_stale:
        conf = classified.get("stale_confidence") or "low"
        out["next_step"] = (
            f"Upload OK but stale_confidence={conf} (see stale_hint). "
            "LOW: smoke first; bump version or force_refresh only if behavior is old. "
            "HIGH (same pack hash): bump metadata.version or "
            "install_path(..., force_refresh=true)."
        )
    else:
        out["next_step"] = (
            "OK. Configure in Dashboard if needed (see dashboard_hints). "
            "Ensure profile plugin_dev_skill (astrbot_ensure_plugin_dev_skill). "
            "User tests in WebChat; Agent does not auto chat_probe. "
            "Dev loop: edit → install_path again; if same-version behavior is stale, "
            "bump version or force_refresh."
        )
    return _dumps(out)


# Process-local pack-hash baseline (plan A): high-confidence stale only when
# same-version re-upload has the same main.py pack hash in this MCP session.
# Missing baseline → stale_confidence=low (conservative, not a false hard fail).
_LAST_PACK_HASH_BY_PLUGIN: dict[str, str] = {}


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
