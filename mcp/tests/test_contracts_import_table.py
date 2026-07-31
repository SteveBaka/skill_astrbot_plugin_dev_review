"""IMPORT_TABLE single-source checks for docs MCP validate_import."""
from __future__ import annotations

from runtime.contracts import IMPORT_TABLE, fuzzy_import_symbols, lookup_import


def test_logger_fix00():
    correct, wrong = lookup_import("logger")
    assert "astrbot.api import logger" in correct
    assert wrong and "astrbot.api.logger" in wrong


def test_filter_not_from_api_root():
    correct, wrong = lookup_import("filter")
    assert "astrbot.api.event import filter" in correct
    assert wrong and "from astrbot.api import filter" in wrong


def test_fuzzy():
    hits = fuzzy_import_symbols("Message")
    assert "AstrMessageEvent" in hits or "MessageChain" in hits or "MessageType" in hits


def test_table_non_empty():
    assert len(IMPORT_TABLE) >= 20
