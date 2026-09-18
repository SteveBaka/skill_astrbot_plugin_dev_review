"""Unit tests for OpenAPI capability matrix + graceful degradation (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from runtime.openapi_caps import (
    OPENAPI_FEATURES,
    feature_status,
    normalize_path,
    parse_core_version,
    version_at_least,
)


def test_normalize_path_collapse_params():
    assert normalize_path("/api/v1/plugins/{plugin_id}/update") == "/api/v1/plugins/{}/update"
    assert normalize_path("/api/v1/plugins/install/url") == "/api/v1/plugins/install/url"


def test_parse_core_version():
    assert parse_core_version("4.28.1") == (4, 28, 1)
    assert parse_core_version("4.27") == (4, 27, 0)
    assert parse_core_version(None) is None
    assert parse_core_version("not-a-version") is None


def test_version_at_least():
    assert version_at_least("4.28.1", "4.27") is True
    assert version_at_least("4.26.8", "4.27") is False
    assert version_at_least(None, "4.27") is None
    assert version_at_least("4.27.0", "4.27") is True


def test_feature_status_old_core_degrades_even_with_snapshot():
    """Docs snapshot must not make an old running core look capable."""
    st = feature_status("install_url", client=None, running_version="4.26.8", use_live=False)
    assert st["status"] == "unsupported"
    assert st.get("degraded") is True
    assert st.get("error_kind") == "core_version_too_old"
    assert st.get("fallback")


def test_feature_status_new_core_supported():
    st = feature_status("install_url", client=None, running_version="4.28.1", use_live=False)
    assert st["status"] == "supported"
    assert st.get("degraded") in (None, False)


def test_feature_matrix_covers_new_openapi_abilities():
    for fid in (
        "install_url",
        "install_git",
        "install_github",
        "plugin_update",
        "plugin_changelog",
        "validate_repo",
        "log_level",
        "install_upload",
    ):
        assert fid in OPENAPI_FEATURES
        assert OPENAPI_FEATURES[fid]["path"].startswith("/api/v1/")
        assert OPENAPI_FEATURES[fid]["min_core"]


def test_snapshot_if_present_has_install_url():
    repo_root = Path(__file__).resolve().parents[2]
    snap = repo_root / "AstrBot OpenAPI v1.json"
    if not snap.is_file():
        return
    data = json.loads(snap.read_text(encoding="utf-8"))
    paths = {normalize_path(p) for p in data.get("paths", {})}
    assert "/api/v1/plugins/install/url" in paths
    assert "/api/v1/plugins/{}/update" in paths
