"""Unit tests for install helpers: zip main hash, fingerprint, stale tiering."""

from __future__ import annotations

import io
import zipfile

from runtime.tools_install import (
    _classify_install_staleness,
    _components_fingerprint,
    _components_look_unchanged,
    _install_fingerprint_compare,
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


def _snap(version: str, command: str = "skillprobe", desc: str = "d") -> dict:
    return {
        "present": True,
        "version": version,
        "components_count": 1,
        "components": _components_fingerprint(
            [{"type": "command", "name": command, "command": command, "description": desc}]
        ),
    }


class TestInstallStalenessTiering:
    """Plan A+D + version evidence (B): bump is not stale."""

    def test_version_bump_same_components_not_stale(self):
        """Repack case: v0.2.0 -> v0.2.1, identical command/docstrings."""
        before = _snap("v0.2.0")
        after = _snap("v0.2.1")
        result = _classify_install_staleness(
            before,
            after,
            refresh_mode="upload_only",
            pack_main_py_sha256_16="e57afb1355a73893",
            last_pack_main_py_sha256_16=None,
        )
        assert result["status"] == "install_ok_version_bumped"
        assert result["possible_stale_install"] is False
        assert result["stale_confidence"] == "none"
        assert result["install_fingerprint"]["version_changed"] is True
        assert result["install_fingerprint"]["version_before"] == "v0.2.0"
        assert result["install_fingerprint"]["version_after"] == "v0.2.1"
        assert "force_refresh" in result["stale_hint"].lower() or "Do NOT" in result["stale_hint"]

    def test_version_and_components_changed_install_ok(self):
        before = _snap("v0.2.0", "a")
        after = _snap("v0.2.1", "b")
        result = _classify_install_staleness(before, after, refresh_mode="upload_only")
        assert result["status"] == "install_ok"
        assert result["possible_stale_install"] is False

    def test_same_version_same_components_unknown_hash_low_stale(self):
        snap = _snap("v0.2.1")
        result = _classify_install_staleness(
            snap,
            dict(snap),
            refresh_mode="upload_only",
            pack_main_py_sha256_16="abc",
            last_pack_main_py_sha256_16=None,
        )
        assert result["status"] == "possible_stale_install"
        assert result["possible_stale_install"] is True
        assert result["stale_confidence"] == "low"

    def test_same_version_same_pack_hash_high_stale(self):
        snap = _snap("v0.2.1")
        result = _classify_install_staleness(
            snap,
            dict(snap),
            refresh_mode="upload_only",
            pack_main_py_sha256_16="deadbeefdeadbeef",
            last_pack_main_py_sha256_16="deadbeefdeadbeef",
        )
        assert result["status"] == "possible_stale_install"
        assert result["stale_confidence"] == "high"

    def test_same_version_pack_hash_changed_not_stale_warning(self):
        snap = _snap("v0.2.1")
        result = _classify_install_staleness(
            snap,
            dict(snap),
            refresh_mode="upload_only",
            pack_main_py_sha256_16="newhashnewhash12",
            last_pack_main_py_sha256_16="oldhasholdhash12",
        )
        assert result["status"] == "pack_changed_components_same"
        assert result["possible_stale_install"] is False

    def test_force_refresh_same_version_not_stale_warning(self):
        snap = _snap("v0.2.1")
        result = _classify_install_staleness(
            snap,
            dict(snap),
            refresh_mode="reinstall_keep_config_data",
            pack_main_py_sha256_16="x",
            last_pack_main_py_sha256_16=None,
        )
        assert result["status"] == "install_ok"
        assert result["possible_stale_install"] is False

    def test_fingerprint_compare_fields(self):
        fp = _install_fingerprint_compare(_snap("1.0.0"), _snap("1.0.1"))
        assert fp["version_changed"] is True
        assert fp["components_same"] is True
        assert any("version" in n for n in fp["notes"])
