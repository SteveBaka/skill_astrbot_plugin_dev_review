"""Unit tests for install helpers: zip main hash, component fingerprint, stale detect."""
from __future__ import annotations

import io
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
