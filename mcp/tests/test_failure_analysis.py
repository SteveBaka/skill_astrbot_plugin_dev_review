"""Unit tests for runtime.failure_analysis — error classification and mining.

Signatures are exercised with realistic tracebacks matching what
star_manager._build_failed_plugin_record stores (source-verified shape).
"""
from __future__ import annotations

from runtime.failure_analysis import (
    analyze_failed_payload,
    analyze_failed_record,
    classify_error,
    extract_plugin_frames,
    traceback_tail,
)

PLUGIN_DIR = "astrbot_plugin_quiz"

TB_IMPORT = f'''Traceback (most recent call last):
  File "/AstrBot/astrbot/core/star/star_manager.py", line 1130, in load
    module = importlib.import_module(module_path)
  File "/AstrBot/data/plugins/{PLUGIN_DIR}/main.py", line 3, in <module>
    from astrbot.api.logger import logger
ModuleNotFoundError: No module named 'astrbot.api.logger'
'''

TB_DEP = f'''Traceback (most recent call last):
  File "/AstrBot/data/plugins/{PLUGIN_DIR}/main.py", line 5, in <module>
    import aiofiles
ModuleNotFoundError: No module named 'aiofiles'
'''

TB_SYNTAX = f'''Traceback (most recent call last):
  File "/AstrBot/data/plugins/{PLUGIN_DIR}/main.py", line 42
    def broken(
              ^
SyntaxError: '(' was never closed
'''


class TestClassify:
    def test_astrbot_logger_import(self):
        c = classify_error("No module named 'astrbot.api.logger'", TB_IMPORT)
        assert c["error_class"] == "wrong_import_path"
        assert c["fix_rule"] == "FIX-00"

    def test_missing_third_party_dep(self):
        c = classify_error("No module named 'aiofiles'", TB_DEP)
        assert c["error_class"] == "missing_dependency"
        assert "requirements.txt" in c["hint"]

    def test_astrbot_import_beats_generic_dep(self):
        # ordering: astrbot-path import errors must NOT be classified as
        # missing third-party dependency
        c = classify_error(
            "ModuleNotFoundError: No module named 'astrbot.core.nothing'"
        )
        assert c["error_class"] == "wrong_import_path"

    def test_syntax_error(self):
        assert classify_error("invalid syntax", TB_SYNTAX)["error_class"] == "syntax_error"

    def test_handler_signature(self):
        c = classify_error("cmd() got multiple values for argument 'text'")
        assert c["fix_rule"] == "FIX-02"

    def test_deprecated_filter(self):
        c = classify_error(
            "AttributeError: module 'astrbot.api.event.filter' has no attribute 'on_keyword'"
        )
        assert c["fix_rule"] == "FIX-21"

    def test_config_not_injected(self):
        c = classify_error("'MyPlugin' object has no attribute 'config'")
        assert c["fix_rule"] == "FIX-22"

    def test_unclassified_gives_kb_hint(self):
        c = classify_error("some totally novel failure")
        assert c["error_class"] == "unclassified"
        assert "auto-fix-guide" in c["hint"]


class TestTracebackMining:
    def test_plugin_frames_prefer_own_code(self):
        frames = extract_plugin_frames(TB_IMPORT, PLUGIN_DIR)
        assert len(frames) == 1
        assert f"{PLUGIN_DIR}/main.py:3" in frames[0]

    def test_frames_fallback_to_last(self):
        frames = extract_plugin_frames(TB_IMPORT, "other_plugin")
        assert frames  # falls back to last frames overall

    def test_tail_has_exception_line(self):
        tail = traceback_tail(TB_IMPORT)
        assert any("ModuleNotFoundError" in ln for ln in tail)

    def test_empty_inputs(self):
        assert extract_plugin_frames("", "x") == []
        assert traceback_tail("") == []


class TestAnalyzeRecord:
    def test_dict_record(self):
        record = {
            "name": PLUGIN_DIR,
            "error": "No module named 'astrbot.api.logger'",
            "traceback": TB_IMPORT,
            "reserved": False,
            "version": "v1.0.0",
        }
        d = analyze_failed_record(PLUGIN_DIR, record)
        assert d["error_class"] == "wrong_import_path"
        assert d["fix_rule"] == "FIX-00"
        assert d["plugin_frames"]
        assert d["version"] == "v1.0.0"

    def test_legacy_string_record(self):
        d = analyze_failed_record("dir_x", "boom happened")
        assert d["dir_name"] == "dir_x"
        assert d["error_class"] == "unclassified"

    def test_long_error_truncated(self):
        d = analyze_failed_record("d", {"error": "x" * 1000, "traceback": ""})
        assert len(d["error"]) <= 301


class TestAnalyzePayload:
    def _payload(self):
        # mirrors API envelope: {status, message, data: {dir: record}}
        return {
            "status": "ok",
            "message": None,
            "data": {
                PLUGIN_DIR: {
                    "name": PLUGIN_DIR,
                    "error": "No module named 'aiofiles'",
                    "traceback": TB_DEP,
                    "reserved": False,
                },
                "plugin_b": {
                    "name": "plugin_b",
                    "error": "invalid syntax",
                    "traceback": TB_SYNTAX,
                    "reserved": False,
                },
            },
        }

    def test_envelope_unwrapped_and_counted(self):
        a = analyze_failed_payload(self._payload())
        assert a["failed_count"] == 2
        assert a["by_class"] == {"missing_dependency": 1, "syntax_error": 1}

    def test_bare_dict_accepted(self):
        a = analyze_failed_payload(self._payload()["data"])
        assert a["failed_count"] == 2

    def test_empty_and_garbage(self):
        assert analyze_failed_payload({})["failed_count"] == 0
        assert analyze_failed_payload(None)["failed_count"] == 0
        assert analyze_failed_payload("nope")["failed_count"] == 0
        assert analyze_failed_payload({"status": "ok", "data": {}})["failed_count"] == 0
