# [RUNTIME P3] WebChat smoke / chat_probe (opt-in, SSE-aware).
"""
POST /api/v1/chat — verified LAN behavior (2026-07):

  Required:
    - API key with **chat** scope
    - username (WebChat owner; e.g. Dashboard user)
    - message
  Config isolation:
    - prefer config_name=plugin_dev_skill (or config_id)
  Session (Plan B, verified 2026-07-27):
    - All probes reuse ONE fixed session id (default "mcp-smoke-<username>");
      server auto-creates it (creator=<username>) when missing and rejects
      reuse by another username → idempotent and safe.
    - Deletion asymmetry (source-verified, chat_service.py): DELETE checks
      session.creator == auth.username, and API-key auth identity is
      "api_key:<key_id>" — so API keys can NEVER delete user-owned sessions.
      The fixed session is managed/deleted by the user in Dashboard WebChat.
    - Do NOT create sessions via /sessions/new for probes: those get
      creator="api_key:<key_id>" and the key_id needed to chat into them is
      only exposed via system-scope /api-keys (privilege escalation — avoided).
  Response:
    - Often text/event-stream style body: lines "data: {json}"
    - JSON envelope status=error may still be HTTP 200

Privacy:
  - confirm_probe=true required (or env ASTRBOT_ALLOW_CHAT_PROBE)
  - Truncate plain text; do not dump full SSE by default
  - Do not write transcripts to disk/repo
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from .client import AstrBotClient
from .config import load_config, mutation_denied_payload

DEFAULT_CONFIG_NAME = "plugin_dev_skill"
DEFAULT_TEXT_LIMIT = 800
DEFAULT_EVENT_LIMIT = 40


def _delete_session(client: AstrBotClient, session_id: str) -> Dict[str, Any]:
    """DELETE /api/v1/chat/sessions/{session_id}; returns compact result."""
    result = client.delete(f"/api/v1/chat/sessions/{session_id}")
    # AstrBot may return HTTP 200 with {"status": "error", ...}
    envelope_error = (
        isinstance(result.data, dict) and result.data.get("status") == "error"
    )
    return {
        "session_id": session_id,
        "deleted": result.ok and not envelope_error,
        "status_code": result.status_code,
        "error": result.error
        or (result.data.get("message") if envelope_error else None),
    }


def _is_webchat_session(s: Dict[str, Any]) -> bool:
    """
    HARD SCOPE: only WebChat-platform sessions are deletable.

    Sessions from other platforms (QQ/Telegram/...) are real user conversations
    (privacy-sensitive); this MCP must never touch them even if the API allows.
    Accepts platform_id == webchat, or umo/session strings like
    "webchat:FriendMessage:webchat!user!uuid".
    """
    pid = str(s.get("platform_id") or s.get("platform") or "").strip().lower()
    if pid == "webchat":
        return True
    for key in ("umo", "unified_msg_origin", "session_id", "id"):
        v = str(s.get(key) or "")
        if v.startswith("webchat:") or v.startswith("webchat!"):
            return True
    return False


def _fetch_webchat_session_ids(
    client: AstrBotClient, username: str, page_size: int
) -> Dict[str, Any]:
    """List sessions for username and return only verified-webchat ids."""
    listed = client.get(
        "/api/v1/chat/sessions",
        params={"username": username, "page": 1, "page_size": max(page_size, 1)},
    )
    if not listed.ok:
        return {"ok": False, "error": listed.error, "error_kind": listed.error_kind}
    data = (
        listed.data.get("data", listed.data)
        if isinstance(listed.data, dict)
        else listed.data
    )
    raw_sessions: List[Any] = []
    if isinstance(data, dict):
        raw_sessions = data.get("sessions") or data.get("items") or []
    elif isinstance(data, list):
        raw_sessions = data
    webchat_ids: List[str] = []
    skipped_non_webchat = 0
    for s in raw_sessions:
        if not isinstance(s, dict):
            continue
        sid = s.get("session_id") or s.get("id")
        if not sid:
            continue
        if _is_webchat_session(s):
            webchat_ids.append(str(sid))
        else:
            skipped_non_webchat += 1
    return {
        "ok": True,
        "webchat_ids": webchat_ids,
        "skipped_non_webchat": skipped_non_webchat,
    }


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _chat_allowed(confirm_probe: bool) -> bool:
    """
    Opt-in: per-call confirm_probe OR host env ASTRBOT_ALLOW_CHAT_PROBE.

    [RUNTIME] Prefer both for automation; interactive agent uses confirm_probe=true
    after user explicitly allows smoke in the conversation.
    """
    if confirm_probe:
        return True
    return _env_bool("ASTRBOT_ALLOW_CHAT_PROBE", False)


def parse_sse_events(raw: str) -> List[Dict[str, Any]]:
    """Parse AstrBot chat SSE body into a list of event dicts."""
    events: List[Dict[str, Any]] = []
    if not raw:
        return events
    # Normalize: handle both \n\n separated and single-line streams
    chunks = raw.replace("\r\n", "\n").split("\n\n")
    for block in chunks:
        block = block.strip()
        if not block:
            continue
        data_lines: List[str] = []
        for line in block.split("\n"):
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            elif line.startswith("data: "):
                data_lines.append(line[6:])
        if not data_lines:
            # whole block might be raw json
            if block.startswith("{"):
                data_lines = [block]
            else:
                continue
        payload = "\n".join(data_lines)
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            events.append({"type": "_unparsed", "data": payload[:300]})
    return events


def summarize_chat_events(
    events: List[Dict[str, Any]],
    *,
    text_limit: int = DEFAULT_TEXT_LIMIT,
    max_events: int = DEFAULT_EVENT_LIMIT,
) -> Dict[str, Any]:
    """Extract agent-friendly fields from SSE events (truncated)."""
    session_id = None
    plains: List[str] = []
    records: List[str] = []
    attachments: List[Any] = []
    errors: List[str] = []
    types: List[str] = []
    ended = False

    for ev in events[:max_events]:
        if not isinstance(ev, dict):
            continue
        t = ev.get("type") or "unknown"
        types.append(str(t))
        if t == "session_id":
            session_id = ev.get("session_id") or ev.get("data") or session_id
        elif t == "plain":
            text = ev.get("data")
            if text is not None:
                s = str(text)
                plains.append(s if len(s) <= text_limit else s[:text_limit] + "…")
        elif t == "record":
            records.append(str(ev.get("data") or ev)[:300])
        elif t in ("attachment_saved", "image", "file"):
            attachments.append(
                {
                    "type": t,
                    "data": str(ev.get("data"))[:200]
                    if not isinstance(ev.get("data"), dict)
                    else {k: ev["data"].get(k) for k in list(ev["data"])[:8]},
                }
            )
        elif t in ("error", "err"):
            errors.append(str(ev.get("data") or ev.get("message") or ev)[:400])
        elif t == "end":
            ended = True
        # ignore user_message_saved / message_saved noise in summary

    return {
        "session_id": session_id,
        "plain_texts": plains,
        "records": records,
        "attachments": attachments,
        "errors": errors,
        "event_types": types,
        "ended": ended,
        "event_count": len(events),
    }


def astrbot_chat_probe(
    message: str,
    *,
    confirm_probe: bool = False,
    username: str = "",
    config_name: str = "",
    config_id: str = "",
    session_id: str = "",
    enable_streaming: bool = False,
    timeout_seconds: float = 0,
) -> str:
    """
    Send one WebChat message and return truncated SSE summary.

    Defaults: config_name=plugin_dev_skill.
    Session policy (Plan B): all smoke probes reuse ONE fixed webchat session
    (default id "mcp-smoke-<username>", override via ASTRBOT_CHAT_SMOKE_SESSION_ID
    or the session_id arg). The session belongs to <username>, so it shows up as
    a single stable entry in Dashboard WebChat where the user can manage or
    delete it. API keys cannot delete user-owned sessions (creator check), so
    the MCP never attempts auto-deletion.
    """
    if not _chat_allowed(confirm_probe):
        return _dumps(
            {
                "ok": False,
                "error_kind": "chat_probe_disabled",
                "error": (
                    "Chat probe blocked. User must explicitly allow smoke testing, "
                    "then call with confirm_probe=true "
                    "(or set ASTRBOT_ALLOW_CHAT_PROBE=true on MCP host)."
                ),
                "hint": (
                    "Main testing remains Dashboard WebChat + plugin_dev_skill. "
                    "MCP probe is optional."
                ),
            }
        )

    msg = (message or "").strip()
    if not msg:
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_request",
                "error": "message is required",
            }
        )

    user = (username or "").strip() or (os.environ.get("ASTRBOT_CHAT_USERNAME") or "").strip()
    if not user:
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_request",
                "error": (
                    "username is required (WebChat session owner). "
                    "Pass username= or set ASTRBOT_CHAT_USERNAME on MCP host."
                ),
            }
        )

    cname = (config_name or "").strip()
    cid = (config_id or "").strip()
    if not cname and not cid:
        cname = (
            (os.environ.get("ASTRBOT_CHAT_CONFIG_NAME") or "").strip()
            or DEFAULT_CONFIG_NAME
        )

    # [RUNTIME] Plan B fixed smoke session (anti-list-spam):
    # ALWAYS land on ONE id per username. Callers used to pass random
    # session_id (e.g. mcp-smoke-types-type2-<uuid>) and flood WebChat.
    # Override only via ASTRBOT_CHAT_SMOKE_SESSION_ID (ops), not per-call
    # session_id — arg is accepted for forward-compat but IGNORED unless it
    # equals the canonical fixed id (explicit reuse).
    # Deletion: API keys get Permission denied (creator=username); user deletes
    # in Dashboard. AstrBot may also log conversation_mgr await-None on delete.
    canonical = (os.environ.get("ASTRBOT_CHAT_SMOKE_SESSION_ID") or "").strip() or (
        f"mcp-smoke-{user}"
    )
    requested = (session_id or "").strip()
    sid = canonical
    session_id_ignored = bool(requested and requested != canonical)
    body: Dict[str, Any] = {
        "message": msg,
        "username": user,
        "session_id": sid,
        "enable_streaming": bool(enable_streaming),
        "flags": {"enable_streaming": bool(enable_streaming)},
    }
    if cname:
        body["config_name"] = cname
    if cid:
        body["config_id"] = cid

    cfg = load_config()
    # Chat may run longer than default plugin list timeout
    timeout = float(timeout_seconds) if timeout_seconds and timeout_seconds > 0 else max(
        float(cfg.timeout), 60.0
    )

    client = AstrBotClient(cfg)
    t0 = time.time()
    result = client.post("/api/v1/chat", json_body=body, timeout=timeout)
    elapsed = round((time.time() - t0) * 1000.0, 2)

    out: Dict[str, Any] = {
        "ok": False,
        "mutation": "chat_probe",
        "elapsed_ms": elapsed,
        "request": {
            "username": user,
            "config_name": cname or None,
            "config_id": cid or None,
            "smoke_session_id": sid,
            "session_id_arg_ignored": session_id_ignored or None,
            "message_preview": msg if len(msg) <= 120 else msg[:120] + "…",
            "enable_streaming": bool(enable_streaming),
        },
        "http": {
            "ok": result.ok,
            "status_code": result.status_code,
            "error": result.error,
            "error_kind": result.error_kind,
            "url": result.url,
        },
        "privacy": (
            "Transcript not stored by MCP. Plain text truncated. "
            "Full SSE raw omitted unless needed for errors."
        ),
    }

    if not result.ok:
        # Auth 403 often = missing chat scope
        if result.error_kind == "auth":
            out["hint"] = (
                "API key may lack chat scope, or token invalid. "
                "Use a key that includes chat + config/plugin as needed."
            )
        out["error"] = result.error
        out["error_kind"] = result.error_kind or "http_error"
        if isinstance(result.data, dict):
            out["server_message"] = result.data.get("message") or result.data.get("status")
        return _dumps(out)

    data = result.data
    # HTTP 200 JSON error envelope
    if isinstance(data, dict) and data.get("status") == "error":
        out["ok"] = False
        out["error_kind"] = "chat_api_error"
        out["error"] = data.get("message") or "chat returned status=error"
        out["server"] = {"status": data.get("status"), "message": data.get("message")}
        if "session_id belongs to another username" in str(data.get("message") or ""):
            out["hint"] = (
                f"Fixed smoke session '{sid}' was created by a different username. "
                "Change username to its owner, or pick a new id via "
                "session_id arg / ASTRBOT_CHAT_SMOKE_SESSION_ID."
            )
        if "Missing key: username" in str(data.get("message") or ""):
            out["hint"] = "Pass username= (Dashboard WebChat user id)."
        return _dumps(out)

    raw_text = ""
    events: List[Dict[str, Any]] = []
    if isinstance(data, dict) and data.get("_raw_text"):
        raw_text = str(data["_raw_text"])
        events = parse_sse_events(raw_text)
    elif isinstance(data, dict) and data.get("status") == "ok":
        # rare non-SSE success
        out["ok"] = True
        out["mode"] = "json_envelope"
        out["data_preview"] = _safe_preview(data.get("data"))
        return _dumps(out)
    elif isinstance(data, str) and data.lstrip().startswith("data:"):
        raw_text = data
        events = parse_sse_events(raw_text)
    else:
        # try treat whole body as SSE-ish
        if isinstance(data, dict):
            out["ok"] = True
            out["mode"] = "json_unknown"
            out["data_preview"] = _safe_preview(data)
            return _dumps(out)
        raw_text = str(data or "")
        events = parse_sse_events(raw_text)

    summary = summarize_chat_events(events)
    out["mode"] = "sse"
    out["summary"] = summary
    # success if we got plain/record/end and no errors
    has_content = bool(summary["plain_texts"] or summary["records"] or summary["attachments"])
    has_err = bool(summary["errors"])
    out["ok"] = has_content and not has_err
    if has_err and not has_content:
        out["error_kind"] = "sse_error"
        out["error"] = summary["errors"][0]
    elif not has_content:
        out["error_kind"] = "empty_response"
        out["error"] = "No plain/record content in SSE (check config/plugin/provider)"
        out["raw_head"] = raw_text[:400] if raw_text else None
    else:
        out["success"] = True
        out["next_step"] = (
            "Interpret plain_texts/records for plugin behavior. "
            "Primary UX test remains Dashboard WebChat."
        )

    out["session_policy"] = (
        f"Forced fixed smoke session '{sid}' (one list entry). "
        "Delete it in Dashboard WebChat while logged in as the session owner — "
        "API keys always get Permission denied; core may also log "
        "conversation_mgr await-None on delete (AstrBot issue, not MCP)."
    )
    if session_id_ignored:
        out["session_policy"] += (
            f" Ignored non-canonical session_id arg '{requested}' to prevent list spam."
        )
    return _dumps(out)


def _safe_preview(obj: Any, limit: int = 600) -> Any:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    if len(s) > limit:
        return s[:limit] + "…"
    if isinstance(obj, (dict, list)):
        return obj
    return s


def astrbot_chat_sessions_brief(username: str = "", page: int = 1, page_size: int = 20) -> str:
    """
    List WebChat sessions for a username (metadata only).

    Note: GET /sessions/{id} may return Permission denied even when listed.
    """
    user = (username or "").strip() or (os.environ.get("ASTRBOT_CHAT_USERNAME") or "").strip()
    client = AstrBotClient()
    params: Dict[str, Any] = {"page": page, "page_size": page_size}
    if user:
        params["username"] = user
    result = client.get("/api/v1/chat/sessions", params=params)
    out: Dict[str, Any] = {
        "ok": result.ok,
        "username_filter": user or None,
        "error": result.error,
        "error_kind": result.error_kind,
        "status_code": result.status_code,
        "privacy": "metadata only; message bodies not fetched",
    }
    if not result.ok:
        if result.error_kind == "auth":
            out["hint"] = "Need API key with chat scope"
        return _dumps(out)
    data = result.data.get("data", result.data) if isinstance(result.data, dict) else result.data
    sessions = []
    total = None
    if isinstance(data, dict):
        sessions = data.get("sessions") or data.get("items") or []
        total = data.get("total")
    elif isinstance(data, list):
        sessions = data
    brief = []
    for s in sessions if isinstance(sessions, list) else []:
        if isinstance(s, dict):
            brief.append(
                {
                    "session_id": s.get("session_id") or s.get("id"),
                    "creator": s.get("creator") or s.get("username"),
                    "display_name": s.get("display_name"),
                    "platform_id": s.get("platform_id"),
                    "created_at": s.get("created_at"),
                }
            )
    out["sessions"] = brief
    out["total"] = total if total is not None else len(brief)
    out["note"] = (
        "Reading a session by id may return Permission denied; "
        "use chat_probe SSE result for smoke content."
    )
    return _dumps(out)


def astrbot_chat_sessions_cleanup(
    session_ids: str = "",
    *,
    username: str = "",
    all_for_username: bool = False,
    confirm_cleanup: bool = False,
    max_delete: int = 50,
) -> str:
    """
    Delete WebChat sessions (batch). Requires mutations + confirm_cleanup.

    KNOWN LIMIT (source-verified): API-key auth identity is "api_key:<key_id>",
    and AstrBot checks session.creator == auth identity — so sessions created
    by Dashboard users return Permission denied here and must be deleted in
    Dashboard WebChat. Only sessions created via this API key are deletable.

    HARD SCOPE: webchat platform only. Every id (including caller-supplied
    session_ids) is verified against the username's webchat session list;
    ids belonging to other platforms/sources are refused, never deleted.

    Modes:
      - session_ids: comma-separated explicit ids (preferred, surgical)
      - all_for_username=true: delete all verified-webchat sessions of username
    Safety:
      - confirm_cleanup must be true (agent asks user first, shows the list)
      - username required in both modes (arg or ASTRBOT_CHAT_USERNAME)
      - hard cap max_delete per call
    """
    cfg = load_config()
    if not cfg.allow_mutations:
        return _dumps(mutation_denied_payload("chat_sessions_cleanup"))
    if not confirm_cleanup:
        return _dumps(
            {
                "ok": False,
                "error_kind": "confirm_required",
                "error": (
                    "confirm_cleanup=true required. Show the user which sessions "
                    "will be deleted (astrbot_chat_sessions_brief) and get explicit OK."
                ),
            }
        )

    requested = [s.strip() for s in (session_ids or "").split(",") if s.strip()]
    user = (username or "").strip() or (os.environ.get("ASTRBOT_CHAT_USERNAME") or "").strip()
    if not user:
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_request",
                "error": (
                    "username is required (arg or ASTRBOT_CHAT_USERNAME) so ids can be "
                    "verified as webchat-only. Refusing unverified delete."
                ),
            }
        )
    if not requested and not all_for_username:
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_request",
                "error": "No session ids to delete (pass session_ids or all_for_username=true).",
            }
        )

    client = AstrBotClient(cfg)

    # Verify against the username's webchat session list (privacy hard-gate):
    # only ids present in this verified list may be deleted.
    fetched = _fetch_webchat_session_ids(
        client, user, page_size=max(max_delete, len(requested), 1)
    )
    if not fetched["ok"]:
        return _dumps(
            {
                "ok": False,
                "error_kind": fetched.get("error_kind") or "http_error",
                "error": f"Failed to list sessions for verification: {fetched.get('error')}",
            }
        )
    verified: List[str] = fetched["webchat_ids"]

    if requested:
        ids = [i for i in requested if i in verified]
        rejected = [i for i in requested if i not in verified]
    else:
        ids = list(verified)
        rejected = []

    if rejected:
        return _dumps(
            {
                "ok": False,
                "error_kind": "scope_violation",
                "error": (
                    f"{len(rejected)} id(s) are not verified webchat sessions of "
                    f"user '{user}' — refusing entire call. Other-platform "
                    "conversations are privacy-protected and never deleted by this MCP."
                ),
                "rejected_ids": rejected[:20],
            }
        )

    if not ids:
        return _dumps(
            {
                "ok": False,
                "error_kind": "nothing_to_delete",
                "error": f"No verified webchat sessions found for user '{user}'.",
                "skipped_non_webchat": fetched.get("skipped_non_webchat", 0),
            }
        )
    if len(ids) > max_delete:
        return _dumps(
            {
                "ok": False,
                "error_kind": "too_many",
                "error": f"{len(ids)} sessions > max_delete={max_delete}. "
                "Raise max_delete explicitly or narrow the list.",
                "session_ids_preview": ids[:20],
            }
        )

    # Prefer batch endpoint; fall back to per-id DELETE if unsupported.
    # NOTE: AstrBot may return HTTP 200 with an error envelope, or 200 without
    # actually deleting — always verify by re-listing afterwards.
    batch = client.post(
        "/api/v1/chat/sessions/batch-delete", json_body={"session_ids": ids}
    )
    batch_envelope_ok = batch.ok and not (
        isinstance(batch.data, dict) and batch.data.get("status") == "error"
    )

    per_id_results: List[Dict[str, Any]] = []
    if not batch_envelope_ok:
        per_id_results = [_delete_session(client, sid) for sid in ids]

    # ── Post-delete verification (authoritative) ───────────────
    recheck = _fetch_webchat_session_ids(client, user, page_size=max(max_delete, 50))
    remaining = (
        [i for i in ids if i in recheck["webchat_ids"]] if recheck["ok"] else None
    )

    if remaining:
        # batch claimed success but sessions survived → retry per-id once
        if batch_envelope_ok and not per_id_results:
            per_id_results = [_delete_session(client, sid) for sid in remaining]
            recheck = _fetch_webchat_session_ids(
                client, user, page_size=max(max_delete, 50)
            )
            remaining = (
                [i for i in ids if i in recheck["webchat_ids"]]
                if recheck["ok"]
                else remaining
            )

    verified_deleted = (
        [i for i in ids if i not in (remaining or [])] if remaining is not None else None
    )
    out: Dict[str, Any] = {
        "ok": remaining == [],
        "mutation": "chat_sessions_cleanup",
        "mode": "batch" if batch_envelope_ok and not per_id_results else "per_id_fallback",
        "requested_count": len(ids),
        "verified_deleted_count": len(verified_deleted) if verified_deleted is not None else None,
        "remaining_ids": remaining,
    }
    if not batch_envelope_ok:
        out["batch_error"] = batch.error or (
            batch.data.get("message") if isinstance(batch.data, dict) else None
        )
    if per_id_results:
        failed = [r for r in per_id_results if not r["deleted"]]
        if failed:
            out["per_id_failed"] = failed
    if remaining is None:
        out["warning"] = "Post-delete verification failed (could not re-list sessions)."
    elif remaining:
        out["error_kind"] = "delete_not_effective"
        out["error"] = (
            f"{len(remaining)} session(s) still present after delete. "
            "API key may lack delete permission, or this AstrBot version "
            "ignores the delete — check Dashboard/AstrBot logs."
        )
    return _dumps(out)
