"""Unit tests for runtime.tools_manage log-level helpers."""
from __future__ import annotations

import json

from runtime.tools_manage import (
    _normalize_log_level,
    astrbot_plugin_log_level_get,
    astrbot_plugin_log_level_set,
)


class TestNormalizeLevel:
    def test_valid_levels(self):
        for lv in ("DEBUG", "info", "Warning", "ERROR", "CRITICAL"):
            api, err = _normalize_log_level(lv)
            assert err is None
            assert api == lv.upper()

    def test_null_aliases(self):
        for a in ("", "none", "global", "null", "default", "  "):
            api, err = _normalize_log_level(a)
            assert err is None and api is None, a

    def test_invalid(self):
        api, err = _normalize_log_level("verbose")
        assert api is None and err and "invalid level" in err


class TestLogLevelGet:
    def test_extracts_only_log_level(self, monkeypatch):
        # config GET returns full config with secrets; tool must return ONLY log_level
        captured = {}

        def _res(**kw):
            return type("R", (), {**kw, "to_dict": lambda self: {k: v for k, v in type(self).__dict__.items() if not callable(v) and not k.startswith("__")}})()
        class FakeClient:
            def get(self, path, **kw):
                captured["path"] = path
                return _res(
                    ok=True, error=None, error_kind=None,
                    data={"status": "ok", "data": {
                        "plugin_name": "astrbot_plugin_x",
                        "log_level": "DEBUG",
                        "config": {"token": "secret-value"},
                    }},
                )

        monkeypatch.setattr("runtime.tools_manage.AstrBotClient", lambda: FakeClient())
        out = json.loads(astrbot_plugin_log_level_get("astrbot_plugin_x"))
        assert out["ok"] is True
        assert out["log_level"] == "DEBUG"
        assert "token" not in out
        assert "config" not in out
        assert "/config" in captured["path"]

    def test_null_level_note(self, monkeypatch):
        def _res(**kw):
            return type("R", (), {**kw, "to_dict": lambda self: {k: v for k, v in type(self).__dict__.items() if not callable(v) and not k.startswith("__")}})()
        class FakeClient:
            def get(self, path, **kw):
                return _res(
                    ok=True, error=None, error_kind=None,
                    data={"status": "ok", "data": {"log_level": None}},
                )

        monkeypatch.setattr("runtime.tools_manage.AstrBotClient", lambda: FakeClient())
        out = json.loads(astrbot_plugin_log_level_get("p"))
        assert out["log_level"] is None
        assert "follows the global" in out.get("note", "")


class TestLogLevelSet:
    def test_mutations_gate(self):
        out = json.loads(astrbot_plugin_log_level_set("p", "DEBUG"))
        assert out["error_kind"] == "mutations_disabled"

    def test_invalid_level(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        out = json.loads(astrbot_plugin_log_level_set("p", "VERBOSE"))
        assert out["error_kind"] == "bad_request"

    def test_put_sends_null_for_global(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        captured = {}

        def _res(**kw):
            return type("R", (), {**kw, "to_dict": lambda self: {k: v for k, v in type(self).__dict__.items() if not callable(v) and not k.startswith("__")}})()
        class FakeClient:
            def put(self, path, json_body, **kw):
                captured["path"] = path
                captured["body"] = json_body
                return _res(
                    ok=True, status_code=200, error=None, error_kind=None,
                    data={"status": "ok", "message": "ok"},
                )

        monkeypatch.setattr("runtime.tools_manage.AstrBotClient", lambda: FakeClient())
        out = json.loads(astrbot_plugin_log_level_set("p", "global"))
        assert out["ok"] is True
        assert captured["body"] == {"level": None}
        assert "log-level" in captured["path"]

    def test_put_sends_enum(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        captured = {}

        def _res(**kw):
            return type("R", (), {**kw, "to_dict": lambda self: {k: v for k, v in type(self).__dict__.items() if not callable(v) and not k.startswith("__")}})()
        class FakeClient:
            def put(self, path, json_body, **kw):
                captured["body"] = json_body
                return _res(
                    ok=True, status_code=200, error=None, error_kind=None,
                    data={"status": "ok", "message": "ok"},
                )

        monkeypatch.setattr("runtime.tools_manage.AstrBotClient", lambda: FakeClient())
        out = json.loads(astrbot_plugin_log_level_set("p", "DEBUG"))
        assert captured["body"] == {"level": "DEBUG"}
        assert out["level_applied"] == "DEBUG"
