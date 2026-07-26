"""Unit tests for runtime.zip_pack — exclusion rules, naming, plugin-shape gates.

Uses the real example plugin plugin-types/type2-session-waiter as the primary
fixture (project decision: test against shipped examples for precision), plus
tmp_path-built trees for exclusion edge cases.
"""
from __future__ import annotations

import io
import zipfile

from runtime.zip_pack import (
    _hard_excluded,
    _safe_zip_token,
    pack_plugin_directory,
    zip_filename_from_metadata,
)


def _zip_names(zip_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return sorted(zf.namelist())


# ── Real example plugin (type2-session-waiter) ─────────────────


class TestPackFixturePlugin:
    def test_pack_ok(self, fixture_plugin_dir):
        r = pack_plugin_directory(fixture_plugin_dir)
        assert r.ok, r.error
        assert r.file_count >= 3  # main.py + metadata.yaml + requirements.txt
        assert r.zip_bytes_size > 0

    def test_metadata_name_becomes_archive_root(self, fixture_plugin_dir):
        # metadata.yaml name (astrbot_plugin_quiz) != dir name (type2-session-waiter):
        # archive root must prefer the metadata name (market/GitHub layout)
        r = pack_plugin_directory(fixture_plugin_dir)
        assert r.metadata_name == "astrbot_plugin_quiz"
        assert r.root_name == "astrbot_plugin_quiz"
        for name in _zip_names(r.zip_bytes):
            assert name.startswith("astrbot_plugin_quiz/")

    def test_zip_filename_strips_v_prefix(self, fixture_plugin_dir):
        # metadata version v1.0.0 → filename ...-1.0.0.zip (no v)
        r = pack_plugin_directory(fixture_plugin_dir)
        assert r.metadata_version == "v1.0.0"
        assert r.zip_filename == "astrbot_plugin_quiz-1.0.0.zip"

    def test_required_files_present(self, fixture_plugin_dir):
        r = pack_plugin_directory(fixture_plugin_dir)
        names = _zip_names(r.zip_bytes)
        assert "astrbot_plugin_quiz/main.py" in names
        assert "astrbot_plugin_quiz/metadata.yaml" in names
        assert "astrbot_plugin_quiz/requirements.txt" in names

    def test_repo_gitignore_junk_never_packed(self, fixture_plugin_dir):
        # repo-root .gitignore is collected walking up; junk must not appear
        r = pack_plugin_directory(fixture_plugin_dir)
        for name in _zip_names(r.zip_bytes):
            assert "__pycache__" not in name
            assert not name.endswith(".pyc")
            assert ".DS_Store" not in name

    def test_deterministic_output(self, fixture_plugin_dir):
        r1 = pack_plugin_directory(fixture_plugin_dir)
        r2 = pack_plugin_directory(fixture_plugin_dir)
        assert _zip_names(r1.zip_bytes) == _zip_names(r2.zip_bytes)
        assert r1.file_count == r2.file_count


# ── Plugin-shape gates ─────────────────────────────────────────


class TestPluginShapeGates:
    def test_missing_metadata_rejected(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1\n")
        r = pack_plugin_directory(tmp_path)
        assert not r.ok
        assert r.error_kind == "not_a_plugin"

    def test_missing_main_rejected(self, tmp_path):
        (tmp_path / "metadata.yaml").write_text("name: astrbot_plugin_x\n")
        r = pack_plugin_directory(tmp_path)
        assert not r.ok
        assert r.error_kind == "not_a_plugin"

    def test_nonexistent_path_rejected(self, tmp_path):
        r = pack_plugin_directory(tmp_path / "nope")
        assert not r.ok
        assert r.error_kind == "bad_path"


# ── Hard exclusion (safety floor, not overridable) ─────────────


def _make_plugin(tmp_path, name="astrbot_plugin_t"):
    (tmp_path / "metadata.yaml").write_text(f"name: {name}\nversion: 1.0.0\n")
    (tmp_path / "main.py").write_text("x = 1\n")
    return tmp_path


class TestHardExcludes:
    def test_hard_dirs_pruned(self, tmp_path):
        root = _make_plugin(tmp_path)
        for d in (".git", ".venv", "__pycache__", "node_modules", ".idea"):
            sub = root / d
            sub.mkdir()
            (sub / "junk.txt").write_text("junk")
        r = pack_plugin_directory(root)
        assert r.ok
        names = _zip_names(r.zip_bytes)
        assert names == [
            "astrbot_plugin_t/main.py",
            "astrbot_plugin_t/metadata.yaml",
        ]

    def test_hard_file_suffixes_skipped(self, tmp_path):
        root = _make_plugin(tmp_path)
        (root / "mod.pyc").write_bytes(b"\x00")
        (root / "lib.so").write_bytes(b"\x00")
        (root / ".DS_Store").write_bytes(b"\x00")
        r = pack_plugin_directory(root)
        names = _zip_names(r.zip_bytes)
        assert "astrbot_plugin_t/mod.pyc" not in names
        assert "astrbot_plugin_t/lib.so" not in names
        assert "astrbot_plugin_t/.DS_Store" not in names

    def test_gitignore_negation_cannot_rescue_hard_excluded(self, tmp_path):
        # Security invariant: '!' in .gitignore must NOT re-include hard-denied dirs
        root = _make_plugin(tmp_path)
        pyc_dir = root / "__pycache__"
        pyc_dir.mkdir()
        (pyc_dir / "cached.pyc").write_bytes(b"\x00")
        (root / ".gitignore").write_text("!__pycache__/\n!*.pyc\n")
        r = pack_plugin_directory(root)
        names = _zip_names(r.zip_bytes)
        assert all("__pycache__" not in n for n in names)

    def test_hard_excluded_unit(self):
        assert _hard_excluded((".venv", "bin"), "python3", False)
        assert _hard_excluded(("pkg.egg-info",), "PKG-INFO", False)
        assert _hard_excluded((), ".DS_Store", False)
        assert _hard_excluded((), "mod.PYC", False)  # case-insensitive suffix
        assert not _hard_excluded(("services",), "api.py", False)


# ── .gitignore layer (plugin-local rules) ──────────────────────


class TestGitignoreLayer:
    def test_plugin_gitignore_respected(self, tmp_path):
        root = _make_plugin(tmp_path)
        (root / "secret.env").write_text("KEY=1")
        (root / "notes.local.md").write_text("x")
        (root / ".gitignore").write_text("secret.env\n*.local.md\n")
        r = pack_plugin_directory(root)
        names = _zip_names(r.zip_bytes)
        assert "astrbot_plugin_t/secret.env" not in names
        assert "astrbot_plugin_t/notes.local.md" not in names
        assert "astrbot_plugin_t/main.py" in names

    def test_gitignored_dir_pruned(self, tmp_path):
        root = _make_plugin(tmp_path)
        logs = root / "logs"
        logs.mkdir()
        (logs / "a.log").write_text("x")
        (root / ".gitignore").write_text("logs/\n")
        r = pack_plugin_directory(root)
        assert all("logs" not in n for n in _zip_names(r.zip_bytes))

    def test_excluded_sample_tagged_with_source(self, tmp_path):
        root = _make_plugin(tmp_path)
        (root / "x.pyc").write_bytes(b"\x00")
        (root / "ignored.txt").write_text("x")
        (root / ".gitignore").write_text("ignored.txt\n")
        r = pack_plugin_directory(root)
        joined = " ".join(r.excluded_sample)
        assert "[hard]" in joined
        assert "[gitignore]" in joined

    def test_all_excluded_returns_empty_pack(self, tmp_path):
        root = _make_plugin(tmp_path)
        (root / ".gitignore").write_text("*\n")
        r = pack_plugin_directory(root)
        assert not r.ok
        assert r.error_kind == "empty_pack"


# ── Naming helpers ─────────────────────────────────────────────


class TestNaming:
    def test_safe_token_strips_v_and_illegal(self):
        assert _safe_zip_token("v2.1.1") == "2.1.1"
        assert _safe_zip_token("my plugin!!") == "my_plugin"
        assert _safe_zip_token("") == "plugin"
        assert _safe_zip_token("vanilla") == "vanilla"  # v + non-digit kept

    def test_zip_filename_variants(self):
        assert (
            zip_filename_from_metadata(
                metadata_name="astrbot_plugin_x", metadata_version="v1.2.3"
            )
            == "astrbot_plugin_x-1.2.3.zip"
        )
        assert (
            zip_filename_from_metadata(metadata_name="astrbot_plugin_x")
            == "astrbot_plugin_x.zip"
        )
        assert (
            zip_filename_from_metadata(metadata_name="", fallback_root="dirname")
            == "dirname.zip"
        )
