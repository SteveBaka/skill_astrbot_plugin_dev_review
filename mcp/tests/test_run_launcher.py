"""Unit tests for mcp/run.py bootstrap decision logic (no exec)."""
from __future__ import annotations

import sys

import pytest

import run as run_launcher

VENV_STR = "/fake/mcp/.venv/bin/python3"


class _FakeVenv:
    def __init__(self, exists: bool):
        self._exists = exists

    def is_file(self) -> bool:
        return self._exists

    def __str__(self) -> str:
        return VENV_STR


@pytest.fixture
def no_system_deps(monkeypatch):
    monkeypatch.setattr(run_launcher, "_import_ok", lambda *a, **k: False)


def test_system_python_has_deps_wins(monkeypatch):
    monkeypatch.setattr(run_launcher, "_import_ok", lambda *a, **k: True)
    assert run_launcher._bootstrap() == sys.executable


def test_existing_venv_importable_used(monkeypatch, no_system_deps):
    monkeypatch.setattr(run_launcher, "_VENV_PY", _FakeVenv(exists=True))

    def import_ok(python, *a, **k):
        return str(python) == VENV_STR

    monkeypatch.setattr(run_launcher, "_import_ok", import_ok)
    assert run_launcher._bootstrap() == VENV_STR


def test_fresh_venv_created_when_needed(monkeypatch, no_system_deps):
    monkeypatch.setattr(run_launcher, "_VENV_PY", _FakeVenv(exists=False))
    created = []

    def _create():
        created.append(True)
        return run_launcher._VENV_PY

    def import_ok(python, *a, **k):
        return str(python) == VENV_STR

    monkeypatch.setattr(run_launcher, "_create_venv", _create)
    monkeypatch.setattr(run_launcher, "_import_ok", import_ok)
    assert run_launcher._bootstrap() == VENV_STR
    assert created


def test_fallback_to_system(monkeypatch, no_system_deps):
    monkeypatch.setattr(run_launcher, "_VENV_PY", _FakeVenv(exists=False))

    def _create():
        raise RuntimeError("venv module missing")

    monkeypatch.setattr(run_launcher, "_create_venv", _create)
    assert run_launcher._bootstrap() == sys.executable
