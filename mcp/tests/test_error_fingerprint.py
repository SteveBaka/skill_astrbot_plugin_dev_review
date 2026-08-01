"""Unit tests for runtime.error_fingerprint — desensitization + KB + propose."""
from __future__ import annotations

import os

import pytest

from runtime.error_fingerprint import (
    FingerprintStore,
    desensitize,
    fingerprint_of,
    max_fix_number,
    propose_fix_entries,
    record_diagnoses_if_enabled,
    validate_fix_entry,
)

RAW = (
    "File \"/AstrBot/data/plugins/astrbot_plugin_quiz/main.py\", line 42, in <module>\n"
    "    from astrbot.api.logger import logger\n"
    "ModuleNotFoundError: No module named 'astrbot.api.logger'"
)


class TestDesensitize:
    def test_strips_paths_uuid_plugin(self):
        out = desensitize(RAW)
        assert "<PATH>" in out
        assert "<N>" in out  # line 42
        assert "astrbot_plugin_quiz" not in out
        assert "/AstrBot/data/plugins" not in out

    def test_bare_plugin_name_tokenized(self):
        out = desensitize("astrbot_plugin_quiz raised ValueError")
        assert "<PLUGIN>" in out
        assert "astrbot_plugin_quiz" not in out

    def test_strips_uuid_and_hex(self):
        s = "session 326b11bd-3337-49f5-8529-bd5efbee6445 hash deadbeefcafebabe1234567890abcdef"
        out = desensitize(s)
        assert "<UUID>" in out
        assert "<HEX>" in out

    def test_strips_token(self):
        out = desensitize("token abk_1234567890abcdef")
        assert "<TOKEN>" in out
        assert "abk_" not in out

    def test_plugin_class(self):
        out = desensitize("MyQuizPlugin raised ValueError")
        assert "<Plugin>" in out
        assert "MyQuizPlugin" not in out

    def test_empty(self):
        assert desensitize("") == ""
        assert desensitize(None) == ""


class TestFingerprint:
    def test_stable_same_input(self):
        a = fingerprint_of(RAW)[0]
        b = fingerprint_of(RAW)[0]
        assert a == b

    def test_differs_on_error(self):
        a = fingerprint_of(RAW)[0]
        b = fingerprint_of("No module named 'aiofiles'")[0]
        assert a != b

    def test_desensitized_sample_no_secrets(self):
        key, sample, meta = fingerprint_of(
            RAW, error_class="wrong_import_path", fix_rule="FIX-00"
        )
        assert meta["fix_rule"] == "FIX-00"
        assert "astrbot_plugin_quiz" not in sample


class TestStore:
    def test_record_increments(self, tmp_path):
        store = FingerprintStore(tmp_path / "kb.json")
        k1 = store.record(RAW, source="t1")
        k2 = store.record(RAW, source="t2")
        assert k1 == k2
        assert store.records[k1]["count"] == 2
        assert set(store.records[k1]["sources"]) == {"t1", "t2"}
        assert (tmp_path / "kb.json").is_file()

    def test_unclassified_filter(self):
        store = FingerprintStore()
        store.record("some novel error here")
        store.record("some novel error here")
        store.record("known one", fix_rule="FIX-00")
        un = store.unclassified(min_occurrences=2)
        assert len(un) == 1
        assert un[0]["fix_rule"] is None

    def test_load_roundtrip(self, tmp_path):
        p = tmp_path / "kb.json"
        s1 = FingerprintStore(p)
        s1.record(RAW, fix_rule="FIX-00")
        s2 = FingerprintStore(p)
        assert s2.to_dict()["total_records"] == 1

    def test_no_path_no_write(self):
        store = FingerprintStore()
        store.record("x")
        assert store.path is None


class TestPropose:
    def test_next_fix_number(self, tmp_path):
        guide = tmp_path / "auto-fix-guide.md"
        guide.write_text("### FIX-29: x\n", encoding="utf-8")
        assert max_fix_number(guide) == 29

    def test_propose_generates_entries(self, tmp_path):
        guide = tmp_path / "auto-fix-guide.md"
        guide.write_text("### FIX-29: x\n", encoding="utf-8")
        store = FingerprintStore()
        store.record("brand new weird failure on widget")
        store.record("brand new weird failure on widget")
        entries = propose_fix_entries(store, guide, min_occurrences=2, max_entries=3)
        assert len(entries) == 1
        assert entries[0]["fix_rule"] == "FIX-30"
        assert entries[0]["occurrences"] == 2
        assert entries[0]["validation"]["ok"] is True

    def test_propose_requires_min(self):
        store = FingerprintStore()
        store.record("one off")
        assert propose_fix_entries(store, "x", min_occurrences=2) == []


class TestValidateFixEntry:
    def _entry(self, sample, pattern=None):
        e = {
            "fix_rule": "FIX-99",
            "title": sample[:60],
            "pattern": pattern or re_escape_placeholder(sample),
            "sample": sample,
        }
        return e

    def test_concrete_sample_ok(self, tmp_path):
        entry = self._entry("weird novel failure inside widget builder")
        v = validate_fix_entry(entry, tmp_path / "missing.md")
        assert v["ok"] is True, v

    def test_placeholder_only_rejected(self, tmp_path):
        entry = self._entry("<PATH> <N> <lit> <TOKEN>")
        v = validate_fix_entry(entry, tmp_path / "missing.md")
        assert v["ok"] is False
        assert any("placeholder_only" in r for r in v["reasons"])

    def test_too_generic_rejected(self, tmp_path):
        # "No module named <lit>" has only 1 concrete token
        entry = self._entry("No module named <lit>")
        v = validate_fix_entry(entry, tmp_path / "missing.md")
        assert v["ok"] is False
        assert any("too_generic" in r for r in v["reasons"])

    def test_duplicate_pattern_in_guide(self, tmp_path):
        sample = "alpha widget exploded in builder"
        guide = tmp_path / "auto-fix-guide.md"
        guide.write_text("### FIX-30: x\n", encoding="utf-8")
        entry = self._entry(sample, pattern="alpha widget exploded in builder")
        # force guide to contain the pattern
        guide.write_text(
            "### FIX-30: x\n\n```python\nre.compile(r\"alpha widget exploded in builder\")\n```\n",
            encoding="utf-8",
        )
        v = validate_fix_entry(entry, guide)
        assert v["ok"] is False
        assert "duplicate_pattern_in_guide" in v["reasons"]

    def test_invalid_pattern_rejected(self, tmp_path):
        entry = self._entry("something went wrong here", pattern="[unclosed")
        v = validate_fix_entry(entry, tmp_path / "missing.md")
        assert v["ok"] is False
        assert any("invalid_pattern" in r for r in v["reasons"])


def re_escape_placeholder(sample: str) -> str:
    import re as _re

    quoted = _re.escape(sample)
    for ph in ("<UUID>", "<HEX>", "<TOKEN>", "<PATH>", "<PLUGIN>", "<Plugin>", "<lit>", "<N>"):
        quoted = quoted.replace(_re.escape(ph), r".+?")
    return quoted


class TestEnvGatedHook:
    def test_no_env_noop(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ASTRBOT_ERROR_KB", raising=False)
        assert record_diagnoses_if_enabled([{"error": "x"}]) == 0

    def test_env_records(self, tmp_path, monkeypatch):
        p = tmp_path / "kb.json"
        monkeypatch.setenv("ASTRBOT_ERROR_KB", str(p))
        diagnoses = [
            {
                "error": "No module named 'aiofiles'",
                "traceback_tail": "  File '<PATH>/main.py', line <N>",
                "error_class": "missing_dependency",
                "fix_rule": None,
            }
        ]
        n = record_diagnoses_if_enabled(diagnoses, source="smoke:test")
        assert n == 1
        assert FingerprintStore(p).to_dict()["total_records"] == 1

    def test_bad_env_no_crash(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ERROR_KB", str(tmp_path / "no" / "dir" / "kb.json"))
        # parent dirs auto-created; still must not raise
        assert record_diagnoses_if_enabled([]) == 0
