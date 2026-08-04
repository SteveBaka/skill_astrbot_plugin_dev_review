"""Unit tests for install helpers: zip main hash, component fingerprint, stale detect."""
from __future__ import annotations

import io
import json
import zipfile

from runtime.tools_install import (
    _components_fingerprint,
    _components_look_unchanged,
    _main_py_hash_from_zip,
)


def _zip_with_main(main_src: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("astrbot_plugin_t/main.py", main_src)
        zf.writestr("astrbot_plugin_t/metadata.yaml", "name: astrbot_plugin_t\n")
    return buf.getvalue()


class TestMainPyHash:
    def test_hash_stable_and_changes_with_content(self):
        a = _main_py_hash_from_zip(_zip_with_main("x = 1\n"))
        b = _main_py_hash_from_zip(_zip_with_main("x = 1\n"))
        c = _main_py_hash_from_zip(_zip_with_main("x = 2\n"))
        assert a and len(a) == 16
        assert a == b
        assert a != c

    def test_missing_main_returns_none(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("astrbot_plugin_t/metadata.yaml", "name: t\n")
        assert _main_py_hash_from_zip(buf.getvalue()) is None


class TestComponentsFingerprint:
    def test_sorted_stable(self):
        comps = [
            {
                "type": "command",
                "name": "b",
                "command": "b",
                "description": "BBB",
            },
            {
                "type": "command",
                "name": "a",
                "command": "a",
                "description": "AAA",
            },
        ]
        fp = _components_fingerprint(comps)
        assert [x["command"] for x in fp] == ["a", "b"]
        assert fp[0]["description"] == "AAA"

    def test_unchanged_detection(self):
        snap = {
            "present": True,
            "version": "1.0.0",
            "components": _components_fingerprint(
                [{"type": "command", "command": "x", "description": "old"}]
            ),
        }
        assert _components_look_unchanged(snap, dict(snap)) is True
        other = {
            "present": True,
            "version": "1.0.0",
            "components": _components_fingerprint(
                [{"type": "command", "command": "x", "description": "new docstring"}]
            ),
        }
        assert _components_look_unchanged(snap, other) is False

    def test_missing_present_not_unchanged(self):
        assert (
            _components_look_unchanged(
                {"present": False},
                {"present": True, "components": []},
            )
            is False
        )


class TestStaleFailedDetection:
    def test_stale_failed_detected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        calls = []

        class FakeResp:
            def __init__(self, ok=True, data=None, error=None, error_kind=None, status_code=200):
                self.ok = ok
                self.data = data
                self.error = error
                self.error_kind = error_kind
                self.status_code = status_code
            def to_dict(self):
                return {"ok": self.ok, "status_code": self.status_code,
                        "error": self.error, "error_kind": self.error_kind, "data": self.data}

        class FakeClient:
            def get(self, path, **kw):
                calls.append(("get", path))
                if path == "/api/v1/plugins/failed":
                    return FakeResp(data={"status": "ok", "data": {"astrbot_plugin_x": {"name": "astrbot_plugin_x", "error": "boom"}}})
                if path.startswith("/api/v1/plugins/astrbot_plugin_x"):
                    return FakeResp(data={"status": "ok", "data": {}})  # present=false
                return FakeResp(data={"status": "ok", "data": {}})
            def delete(self, path, json_body=None, **kw):
                calls.append(("delete", path, json_body))
                return FakeResp(data={"status": "ok", "message": "ok"})
            def post(self, path, json_body=None, **kw):
                calls.append(("post", path))
                return FakeResp(data={"status": "ok", "data": {"name": "astrbot_plugin_x"}})
            def patch(self, path, json_body=None, **kw):
                calls.append(("patch", path))
                return FakeResp(data={"status": "ok", "data": {}})
            def post_multipart(self, path, files=None, data=None, **kw):
                calls.append(("upload",))
                return FakeResp(data={"status": "ok", "data": {"name": "astrbot_plugin_x"}})

        monkeypatch.setattr("runtime.tools_install.AstrBotClient", lambda cfg=None: FakeClient())

        from runtime.tools_install import astrbot_plugin_install_path
        root = tmp_path / "astrbot_plugin_x"
        root.mkdir()
        (root / "metadata.yaml").write_text("name: astrbot_plugin_x\nversion: 0.1.0\nauthor: t\n")
        (root / "main.py").write_text("x = 1\n")

        # without clear_failed: detects stale but doesn't delete
        r = json.loads(astrbot_plugin_install_path(str(root)))
        assert r["stale_failed"] and r["stale_failed"]["detected"] is True
        assert not any(c[0] == "delete" for c in calls)

        # with clear_failed: deletes failed record before upload
        r2 = json.loads(astrbot_plugin_install_path(str(root), clear_failed=True))
        dels = [c for c in calls if c[0] == "delete"]
        assert dels and "plugins/failed" in dels[0][1]
        assert r2["refresh_mode"] == "cleared_failed_then_upload"
