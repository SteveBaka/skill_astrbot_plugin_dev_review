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
      "api_key:<key_id>". Consequence: an API key can never delete a session
      owned by a WebChat username. To make smoke sessions auto-deletable, set
      the owner (ASTRBOT_CHAT_USERNAME) to this key's identity "api_key:<key_id>"
      — then creator == auth identity and cleanup works. The probe reports the
      resolved mode as cleanup.mode (auto / manual / unknown).
    - Do NOT create sessions via /sessions/new for probes: those get
      creator="api_key:<key_id>" while the chat body still needs a matching
      owner string, and key_id is only exposed via system-scope /api-keys
      (privilege escalation — avoided).
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
import re
import time
from typing import Any
from urllib.parse import quote

from .client import AstrBotClient
from .config import load_config, mutation_denied_payload

DEFAULT_CONFIG_NAME = "plugin_dev_skill"
DEFAULT_TEXT_LIMIT = 800
DEFAULT_EVENT_LIMIT = 40

# Conversation fallback only ever touches ids with this prefix — real user
# conversations are never deleted even though the endpoint would permit it.
SMOKE_SESSION_PREFIX = "mcp-smoke-"

# AstrBot builds an API-key caller's auth identity as f"{API_KEY_USERNAME_PREFIX}{key_id}"
# (core: astrbot/core/workspace.py). DELETE /chat/sessions/{id} requires
# session.creator == that identity, so a smoke session is auto-deletable only when it was
# created under this exact owner string.
API_KEY_OWNER_PREFIX = "api_key:"


def _delete_session(client: AstrBotClient, session_id: str) -> dict[str, Any]:
    """DELETE /api/v1/chat/sessions/{session_id}; returns compact result."""
    result = client.delete(f"/api/v1/chat/sessions/{session_id}")
    # AstrBot may return HTTP 200 with {"status": "error", ...}
    envelope_error = isinstance(result.data, dict) and result.data.get("status") == "error"
    return {
        "session_id": session_id,
        "deleted": result.ok and not envelope_error,
        "status_code": result.status_code,
        "error": result.error or (result.data.get("message") if envelope_error else None),
    }


def _smoke_conversation_umo(creator: str, session_id: str) -> str:
    """WebChat private-chat UMO (mirrors chat_service.build_webchat_unified_msg_origin)."""
    return f"webchat:FriendMessage:webchat!{creator}!{session_id}"


def _list_smoke_conversations(
    client: AstrBotClient, creator: str, session_ids: list[str]
) -> dict[str, Any]:
    """Map smoke session ids → real conversation cids via the `data` scope.

    `DELETE /api/v1/conversations/{id}` takes a conversation **uuid** (`cid`), NOT a
    session id; passing a session id matches zero rows and still returns 200. So the
    cid must be read from the list endpoint (which returns `cid` + `user_id`) before
    anything is deleted.
    """
    wanted = {sid for sid in session_ids if sid.startswith(SMOKE_SESSION_PREFIX)}
    found: dict[str, list[dict[str, Any]]] = {}
    scanned = 0
    if not wanted:
        return {"ok": True, "cids": found, "scanned": 0}

    page = 1
    while page <= 20:
        res = client.get(
            "/api/v1/conversations",
            params={
                "page": page,
                "page_size": 100,
                "platforms": "webchat",
                "include_history": "false",
                "umo": "",  # server-side umo filter is a substring match; scan instead
            },
        )
        if not res.ok:
            return {"ok": False, "error": res.error, "error_kind": res.error_kind}
        payload = res.data.get("data", res.data) if isinstance(res.data, dict) else res.data
        items = (payload or {}).get("conversations") or []
        for item in items:
            scanned += 1
            if not isinstance(item, dict):
                continue
            umo = str(item.get("user_id") or "")
            # Only this smoke owner's sessions are relevant.
            if f"!{creator}!" not in umo:
                continue
            sid = umo.rsplit("!", 1)[-1]
            if sid in wanted and item.get("cid"):
                found.setdefault(sid, []).append(
                    {"cid": str(item["cid"]), "user_id": umo}
                )
        pagination = (payload or {}).get("pagination") or {}
        if page >= int(pagination.get("total_pages") or 1):
            break
        page += 1

    return {"ok": True, "cids": found, "scanned": scanned}


def _delete_smoke_conversations(
    client: AstrBotClient, creator: str, session_ids: list[str]
) -> dict[str, Any]:
    """Remove the user-visible conversation(s) of smoke sessions via the `data` scope.

    `DELETE /api/v1/chat/sessions/{id}` is creator-gated, so an API key can never
    remove a session owned by a WebChat username. The conversation endpoints differ:
    they take `user_id`/`cid` as parameters and need only the `data` scope
    (astrbot/dashboard/api/conversations.py), which is what the Dashboard itself uses.

    Correct sequence — and the reason this needs two calls:
      1. GET  /api/v1/conversations?platforms=webchat  → real `cid` per session
      2. DELETE /api/v1/conversations/{cid}?user_id=<umo>
      3. GET  the list again → verify the cid is gone

    HARD SCOPE: only `mcp-smoke-*` session ids are considered. Real conversations are
    never deleted even though this endpoint would technically allow it.
    """
    deleted: list[str] = []
    refused: list[str] = []
    failures: list[dict[str, Any]] = []
    verified: list[str] = []

    for sid in session_ids:
        if not sid.startswith(SMOKE_SESSION_PREFIX):
            refused.append(sid)

    lookup = _list_smoke_conversations(client, creator, session_ids)
    if not lookup.get("ok"):
        return {
            "deleted": False,
            "deleted_ids": [],
            "refused_non_smoke_ids": refused,
            "failures": [{"error": lookup.get("error"), "stage": "list"}],
            "via": "GET+DELETE /api/v1/conversations (scope: data)",
        }

    cids_by_session: dict[str, list[dict[str, Any]]] = lookup["cids"]

    for sid, entries in cids_by_session.items():
        for entry in entries:
            cid = entry["cid"]
            res = client.delete(
                "/api/v1/conversations/" + quote(cid, safe=""),
                params={"user_id": entry["user_id"]},
            )
            envelope_error = isinstance(res.data, dict) and res.data.get("status") == "error"
            if envelope_error:
                failures.append(
                    {
                        "session_id": sid,
                        "cid": cid,
                        "status_code": res.status_code,
                        "error": res.data.get("message") or "error envelope",
                    }
                )
            elif not res.ok:
                failures.append(
                    {
                        "session_id": sid,
                        "cid": cid,
                        "status_code": res.status_code,
                        "error": res.error,
                    }
                )
            else:
                deleted.append(sid)

    # Verification is mandatory: this endpoint returns 200 for a non-existent cid too,
    # so `res.ok` alone has already produced a false success once.
    if deleted:
        recheck = _list_smoke_conversations(client, creator, deleted)
        if recheck.get("ok"):
            still_there = set(recheck["cids"])
            verified = [s for s in deleted if s not in still_there]
            vanished = [s for s in deleted if s in still_there]
            if vanished:
                failures.append(
                    {
                        "stage": "verify",
                        "error": "conversation(s) still listed after delete",
                        "session_ids": vanished,
                    }
                )
                deleted = verified

    return {
        "deleted": bool(deleted) and not failures,
        "deleted_ids": deleted,
        "refused_non_smoke_ids": refused,
        "failures": failures,
        "scanned": lookup.get("scanned"),
        # Nothing found is "already clean", not "failed" — a second run on an
        # already-cleaned owner must not look like an error.
        "already_absent": not cids_by_session,
        "via": "GET+DELETE /api/v1/conversations (scope: data)",
    }


def _is_webchat_session(s: dict[str, Any]) -> bool:
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
) -> dict[str, Any]:
    """List sessions for username and return only verified-webchat ids."""
    listed = client.get(
        "/api/v1/chat/sessions",
        params={"username": username, "page": 1, "page_size": max(page_size, 1)},
    )
    if not listed.ok:
        return {"ok": False, "error": listed.error, "error_kind": listed.error_kind}
    data = listed.data.get("data", listed.data) if isinstance(listed.data, dict) else listed.data
    raw_sessions: list[Any] = []
    if isinstance(data, dict):
        raw_sessions = data.get("sessions") or data.get("items") or []
    elif isinstance(data, list):
        raw_sessions = data
    webchat_ids: list[str] = []
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


def _cleanup_policy(client: AstrBotClient, owner: str, sid: str) -> dict[str, Any]:
    """Report whether this smoke session can be auto-deleted by the same API key.

    Verified server-side rule: DELETE /chat/sessions/{id} rejects unless
    ``session.creator == auth identity``, and an API key's identity is
    ``api_key:<key_id>``. A session is therefore auto-deletable only when it was
    created under that exact owner string — never assume, because a wrong owner
    surfaces much later as an unexplained "Permission denied".
    """
    if not owner.startswith(API_KEY_OWNER_PREFIX):
        return {
            "mode": "manual",
            "owner": owner,
            "owner_is_api_key_identity": False,
            "reason": (
                "Session is owned by a WebChat username, so an API key cannot delete it "
                "(creator check). Delete it in Dashboard WebChat — or set "
                f"ASTRBOT_CHAT_USERNAME={API_KEY_OWNER_PREFIX}<key_id> to make smoke "
                "sessions API-key-owned and auto-deletable."
            ),
        }

    listed = _fetch_webchat_session_ids(client, owner, page_size=50)
    if not listed.get("ok"):
        return {
            "mode": "unknown",
            "owner": owner,
            "owner_is_api_key_identity": True,
            "error": listed.get("error"),
            "reason": "Could not list sessions under this owner to verify auto-cleanup.",
        }

    present = sid in listed.get("webchat_ids", [])
    policy: dict[str, Any] = {
        "mode": "auto" if present else "manual",
        "owner": owner,
        "owner_is_api_key_identity": True,
        "session_listed_under_owner": present,
    }
    policy["reason"] = (
        "Session is owned by this API key → astrbot_chat_sessions_cleanup can delete it "
        "(pass the same username/owner)."
        if present
        else (
            "Probe succeeded but the session is NOT listed under this owner, so the owner "
            "string probably does not match this key's real identity. Auto-cleanup would "
            "fail — read key_id from Dashboard → API keys, or delete manually."
        )
    )
    return policy


def _attach_cleanup(
    out: dict[str, Any],
    client: AstrBotClient,
    owner: str,
    sid: str,
    session_id_ignored: bool,
    auto_cleanup: dict[str, Any] | None = None,
) -> None:
    """Attach cleanup policy + session_policy text to a probe result (mutates out)."""
    policy = _cleanup_policy(client, owner, sid)
    out["cleanup"] = policy
    if auto_cleanup is not None:
        out["cleanup"]["auto"] = auto_cleanup

    text = f"Forced fixed smoke session '{sid}' (one list entry). "
    if auto_cleanup is not None and auto_cleanup.get("attempted"):
        if auto_cleanup.get("cleaned"):
            text += "Removed automatically after this probe (conversation cleanup)."
        else:
            text += "Auto-cleanup was attempted but did not remove it — see cleanup.auto."
    elif policy["mode"] == "auto":
        text += "Owned by this API key → astrbot_chat_sessions_cleanup can delete it."
    elif policy["mode"] == "unknown":
        text += "Ownership unverified — delete it in Dashboard WebChat to be safe."
    else:
        text += (
            "Delete it in Dashboard WebChat while logged in as the session owner — an "
            "API key gets Permission denied (creator check); core may also log "
            "conversation_mgr await-None on delete (AstrBot issue, not MCP)."
        )
    if session_id_ignored:
        text += " Ignored non-canonical session_id arg to prevent list spam."
    out["session_policy"] = text


def cleanup_smoke_workspace(
    client: AstrBotClient,
    owner: str,
    *,
    extra_session_ids: list[str] | None = None,
    cap: int = 20,
) -> dict[str, Any]:
    """Remove every leftover smoke artifact for one owner — the hygiene half of a probe.

    Two targets, both restricted to `mcp-smoke-*`:
      * the session(s) this run just created (`extra_session_ids`);
      * older sessions this owner left behind (a crashed probe, an interrupted run),
        discovered by listing the owner's webchat sessions.

    Session rows created for a WebChat username cannot be deleted by an API key, but
    their conversations can (see `_delete_smoke_conversations`), which is what a user
    actually sees in Dashboard → Data & Logs → Conversations.

    Returns a compact, JSON-safe report; never raises.
    """
    found: set[str] = set(s for s in (extra_session_ids or []) if s.startswith(SMOKE_SESSION_PREFIX))

    listed = _fetch_webchat_session_ids(client, owner, page_size=100)
    stale_discovered: list[str] = []
    if listed.get("ok"):
        for sid in listed.get("webchat_ids", []):
            if sid.startswith(SMOKE_SESSION_PREFIX) and sid not in found:
                stale_discovered.append(sid)
                found.add(sid)

    targets = sorted(found)[:cap]
    truncated = len(found) > cap

    session_attempt = [_delete_session(client, sid) for sid in targets] if targets else []
    session_deleted = [r["session_id"] for r in session_attempt if r["deleted"]]

    conv = (
        _delete_smoke_conversations(client, owner, targets)
        if targets
        else {
            "deleted": False,
            "deleted_ids": [],
            "refused_non_smoke_ids": [],
            "failures": [],
            "via": "noop",
        }
    )

    report: dict[str, Any] = {
        "attempted": bool(targets),
        "owner": owner,
        "targets": targets,
        "stale_discovered": sorted(stale_discovered),
        "session_rows_deleted": session_deleted,
        "conversation_cleanup": conv,
        "cleaned": bool(targets) and not conv.get("failures"),
    }
    if listed.get("ok") is False:
        report["list_error"] = listed.get("error")
    if truncated:
        report["truncated_at"] = cap
        report["note"] = "More leftovers than the per-run cap; run cleanup again to drain."
    if not targets:
        report["cleaned"] = True  # nothing to clean is a clean environment
        report["note"] = "No smoke leftovers for this owner."
    return report


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


def parse_sse_events(raw: str) -> list[dict[str, Any]]:
    """Parse AstrBot chat SSE body into a list of event dicts."""
    events: list[dict[str, Any]] = []
    if not raw:
        return events
    # Normalize: handle both \n\n separated and single-line streams
    chunks = raw.replace("\r\n", "\n").split("\n\n")
    for block in chunks:
        block = block.strip()
        if not block:
            continue
        data_lines: list[str] = []
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


# AstrBot renders streamed model reasoning through the plain channel. Require the
# full marker (emoji + label + colon, or the bare label + colon) so that a plugin
# printing an emoji-led message is not mistaken for reasoning.
_REASONING_RE = re.compile(
    r"^\s*(?:🤔\s*(?:思考|thinking)\s*[:：]|(?:思考|thinking)\s*[:：])",
    re.IGNORECASE,
)


def is_reasoning_text(text: str) -> bool:
    """True when a `plain` chunk is model reasoning, not user-visible plugin output."""
    return bool(_REASONING_RE.match(text or ""))


def summarize_chat_events(
    events: list[dict[str, Any]],
    *,
    text_limit: int = DEFAULT_TEXT_LIMIT,
    max_events: int = DEFAULT_EVENT_LIMIT,
) -> dict[str, Any]:
    """Extract agent-friendly fields from SSE events (truncated)."""
    session_id = None
    plains: list[str] = []
    reasoning: list[str] = []
    records: list[str] = []
    attachments: list[Any] = []
    errors: list[str] = []
    types: list[str] = []
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
                s = s if len(s) <= text_limit else s[:text_limit] + "…"
                # AstrBot renders model reasoning through the plain channel with a
                # leading marker. Keeping it in `plain_texts` made LLM chit-chat look
                # like plugin output (a case that "passed" without the command running).
                if is_reasoning_text(s):
                    reasoning.append(s)
                else:
                    plains.append(s)
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
        "reasoning": reasoning,
        "records": records,
        "attachments": attachments,
        "errors": errors,
        "event_types": types,
        "ended": ended,
        "event_count": len(events),
    }


def _smoke_deadline(request_timeout: float) -> float:
    """Overall wall-clock cap for one chat probe.

    Two constraints meet here:
      * the read must be bounded at all, or a never-ending SSE stream blocks the whole
        MCP process (observed live on AstrBot 4.29.0);
      * the call should finish inside a typical MCP client window (~30 s), because a
        client-side timeout discards the parsed events — a truthful truncated result is
        still actionable, a lost one is not.
    Raise ASTRBOT_CHAT_SMOKE_DEADLINE when the client allows a longer window.
    """
    cap = max(0.0, float(request_timeout)) + 15.0
    try:
        client_window = float(os.environ.get("ASTRBOT_CHAT_SMOKE_DEADLINE") or 25.0)
    except ValueError:
        client_window = 25.0
    if client_window > 0:
        cap = min(cap, client_window)
    return cap


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
    auto_cleanup: bool = False,
) -> str:
    """
    Send one WebChat message and return truncated SSE summary.

    Defaults: config_name=plugin_dev_skill.
    Session policy (Plan B): all smoke probes reuse ONE fixed webchat session
    (default id "mcp-smoke-<username>", override via ASTRBOT_CHAT_SMOKE_SESSION_ID
    or the session_id arg). The session's creator is the `username` we send.

    Cleanup — two modes, decided by that owner string:
      - owner is a WebChat username  → creator is that user, so an API key gets
        "Permission denied" on DELETE; the user removes it in Dashboard WebChat.
      - owner is the key's identity  → set
        ASTRBOT_CHAT_USERNAME=api_key:<key_id> (Dashboard → API keys shows key_id).
        The session becomes API-key-owned, so astrbot_chat_sessions_cleanup can
        delete it. The result reports cleanup.mode ("auto"/"manual"/"unknown")
        and verifies the session really is listed under that owner.

    MESSAGE: pass the PLUGIN'S OWN command (from plugin_get / smoke_suite
    components). Use "/plugin_help" as a minimal discovery probe when unsure;
    never hardcode other plugins' commands like "/ttsinfo".
    """
    def _finish(result: dict) -> str:
        """Attach cleanup policy, optionally perform auto-cleanup, then serialise.

        `client` is created later in this function, so a bound reference here would
        capture nothing; the cleanup calls build their own client (cheap, one per run).
        """
        probe_client = AstrBotClient(load_config())
        auto_report = None
        if auto_cleanup:
            auto_report = cleanup_smoke_workspace(
                probe_client, user, extra_session_ids=[sid]
            )
        _attach_cleanup(result, probe_client, user, sid, session_id_ignored, auto_report)
        return _dumps(result)

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
        cname = (os.environ.get("ASTRBOT_CHAT_CONFIG_NAME") or "").strip() or DEFAULT_CONFIG_NAME

    # [RUNTIME] Plan B fixed smoke session (anti-list-spam):
    # ALWAYS land on ONE id per username. Callers used to pass random
    # session_id (e.g. mcp-smoke-types-type2-<uuid>) and flood WebChat.
    # Override only via ASTRBOT_CHAT_SMOKE_SESSION_ID (ops), not per-call
    # session_id — arg is accepted for forward-compat but IGNORED unless it
    # equals the canonical fixed id (explicit reuse).
    # Deletion: only an API-key-owned session (owner == "api_key:<key_id>") is
    # deletable by this key; a username-owned one is removed in Dashboard.
    # AstrBot may also log conversation_mgr await-None on delete.
    canonical = (os.environ.get("ASTRBOT_CHAT_SMOKE_SESSION_ID") or "").strip() or (
        # ":" is legal but reads badly in URLs/logs; only key-owner ids are affected,
        # plain usernames are unchanged.
        f"mcp-smoke-{user.replace(':', '-')}"
    )
    requested = (session_id or "").strip()
    sid = canonical
    session_id_ignored = bool(requested and requested != canonical)
    body: dict[str, Any] = {
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
    timeout = (
        float(timeout_seconds)
        if timeout_seconds and timeout_seconds > 0
        else max(float(cfg.timeout), 60.0)
    )

    client = AstrBotClient(cfg)
    t0 = time.time()
    # Hard overall cap — see _smoke_deadline for why it is bounded and client-safe.
    result = client.post(
        "/api/v1/chat",
        json_body=body,
        timeout=timeout,
        max_total_seconds=_smoke_deadline(timeout),
    )
    elapsed = round((time.time() - t0) * 1000.0, 2)

    out: dict[str, Any] = {
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
    # Explicit, non-breaking signal: `ok` keeps its meaning, but a truncated stream
    # means the plugin's full output may not have arrived (summary.ended is false too).
    out["truncated"] = result.error_kind == "stream_truncated"

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
        if "reserved for an AstrBot administrator" in str(data.get("message") or ""):
            # AstrBot only lets a key act as an admin id when the key carries the
            # chat:admin sensitive sub-scope (open_api_service.prepare_chat_send).
            out["error_kind"] = "admin_username_needs_chat_admin"
            out["hint"] = (
                f"'{user}' is in an AstrBot profile's admins_id. Sending as an admin "
                "requires the API key to hold the sensitive sub-scope 'chat:admin' "
                "(Dashboard → API keys; it also requires 'chat'). Either grant it, or "
                "use a non-admin owner — e.g. leave ASTRBOT_CHAT_USERNAME on a plain "
                "smoke username."
            )
        return _dumps(out)

    raw_text = ""
    events: list[dict[str, Any]] = []
    if isinstance(data, dict) and data.get("_raw_text"):
        raw_text = str(data["_raw_text"])
        events = parse_sse_events(raw_text)
    elif isinstance(data, dict) and data.get("status") == "ok":
        # rare non-SSE success
        out["ok"] = True
        out["mode"] = "json_envelope"
        out["data_preview"] = _safe_preview(data.get("data"))
        return _finish(out)
    elif isinstance(data, str) and data.lstrip().startswith("data:"):
        raw_text = data
        events = parse_sse_events(raw_text)
    else:
        # try treat whole body as SSE-ish
        if isinstance(data, dict):
            out["ok"] = True
            out["mode"] = "json_unknown"
            out["data_preview"] = _safe_preview(data)
            return _finish(out)
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

    return _finish(out)


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
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if user:
        params["username"] = user
    result = client.get("/api/v1/chat/sessions", params=params)
    out: dict[str, Any] = {
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

    KNOWN LIMIT (source-verified): AstrBot checks session.creator == auth identity
    on DELETE, and an API-key caller's identity is "api_key:<key_id>". So this tool
    can delete ONLY sessions whose creator is exactly that key identity — i.e. smoke
    sessions created by astrbot_chat_probe while ASTRBOT_CHAT_USERNAME (its owner) is
    that same "api_key:<key_id>" string. Sessions created for a WebChat username
    return Permission denied and must be deleted in Dashboard WebChat.

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
    fetched = _fetch_webchat_session_ids(client, user, page_size=max(max_delete, len(requested), 1))
    if not fetched["ok"]:
        return _dumps(
            {
                "ok": False,
                "error_kind": fetched.get("error_kind") or "http_error",
                "error": f"Failed to list sessions for verification: {fetched.get('error')}",
            }
        )
    verified: list[str] = fetched["webchat_ids"]

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
    batch = client.post("/api/v1/chat/sessions/batch-delete", json_body={"session_ids": ids})
    batch_envelope_ok = batch.ok and not (
        isinstance(batch.data, dict) and batch.data.get("status") == "error"
    )

    per_id_results: list[dict[str, Any]] = []
    if not batch_envelope_ok:
        per_id_results = [_delete_session(client, sid) for sid in ids]

    # ── Post-delete verification (authoritative) ───────────────
    recheck = _fetch_webchat_session_ids(client, user, page_size=max(max_delete, 50))
    remaining = [i for i in ids if i in recheck["webchat_ids"]] if recheck["ok"] else None

    if remaining:
        # batch claimed success but sessions survived → retry per-id once
        if batch_envelope_ok and not per_id_results:
            per_id_results = [_delete_session(client, sid) for sid in remaining]
            recheck = _fetch_webchat_session_ids(client, user, page_size=max(max_delete, 50))
            remaining = (
                [i for i in ids if i in recheck["webchat_ids"]] if recheck["ok"] else remaining
            )

    # Fallback: the chat-session DELETE is creator-gated, so a session owned by a
    # WebChat username can never be removed by an API key. The conversation endpoint
    # is a different story — it takes user_id as a *parameter* and only needs the
    # `data` scope (astrbot/dashboard/api/conversations.py:235-248), so the chat entry
    # the user actually sees can still be removed. Strictly limited to smoke ids.
    conversation_result: dict[str, Any] | None = None
    if remaining:
        conversation_result = _delete_smoke_conversations(client, user, remaining)

    verified_deleted = (
        [i for i in ids if i not in (remaining or [])] if remaining is not None else None
    )
    out: dict[str, Any] = {
        "ok": remaining == [],
        "mutation": "chat_sessions_cleanup",
        "mode": "batch" if batch_envelope_ok and not per_id_results else "per_id_fallback",
        "requested_count": len(ids),
        "verified_deleted_count": len(verified_deleted) if verified_deleted is not None else None,
        "remaining_ids": remaining,
    }
    if conversation_result is not None:
        out["conversation_fallback"] = conversation_result
        # A removed conversation is often the outcome that matters: the platform
        # session row may linger while the user-visible chat entry is gone.
        if conversation_result.get("deleted"):
            out["ok"] = True
            out["note"] = (
                "Chat-session DELETE was refused (creator gate), but the conversation "
                "itself was deleted via the data scope — it no longer appears in "
                "Dashboard → Data & Logs → Conversations. The underlying platform "
                "session row may persist; that is an AstrBot-side asymmetry, not a "
                "failure of this call."
            )
    if not batch_envelope_ok:
        out["batch_error"] = batch.error or (
            batch.data.get("message") if isinstance(batch.data, dict) else None
        )
    if per_id_results:
        failed = [r for r in per_id_results if not r["deleted"]]
        if failed:
            out["per_id_failed"] = failed
    conversation_done = bool(conversation_result and conversation_result.get("deleted"))
    conversation_absent = bool(
        conversation_result and conversation_result.get("already_absent")
    )
    if conversation_absent:
        # Nothing left to delete: the conversation was already gone (e.g. a previous
        # run cleaned it). The session row may still exist, so report it as retained
        # rather than as a failed delete.
        out["session_row_retained"] = bool(remaining)
        out["ok"] = True
        out["note"] = (
            "No conversation to remove for the requested id(s) — already cleaned. "
            + (
                "The platform session row is still present (creator gate); it is not "
                "a user-visible conversation."
                if remaining
                else ""
            )
        ).strip()
        return _dumps(out)
    if remaining is None:
        out["warning"] = "Post-delete verification failed (could not re-list sessions)."
    elif remaining and conversation_done:
        # The platform session row survived (creator gate), but the user-visible
        # conversation is gone. Reporting an error here would contradict ok=true.
        out["session_row_retained"] = True
        out.setdefault("note", "")
        out["note"] += (
            " The platform session row for "
            f"{', '.join(conversation_result['deleted_ids'])} was retained by core "
            "(creator gate); it is not a user-visible conversation."
        )
    elif remaining:
        out["error_kind"] = "delete_not_effective"
        out["error"] = (
            f"{len(remaining)} session(s) still present after delete. "
            "API key may lack delete permission, or this AstrBot version "
            "ignores the delete — check Dashboard/AstrBot logs."
        )
    return _dumps(out)
