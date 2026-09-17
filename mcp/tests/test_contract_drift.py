"""Unit tests for runtime.contract_drift — filter API export parsing + drift."""

from __future__ import annotations

from runtime.contract_drift import drift_report, parse_filter_api_exports
from runtime.contracts import FILTER_ATTR_KNOWN

MASTER_STYLE = """
from astrbot.core.star.filter.custom_filter import CustomFilter
from astrbot.core.star.filter.event_message_type import (
    EventMessageType,
    EventMessageTypeFilter,
)
from astrbot.core.star.filter.permission import PermissionType, PermissionTypeFilter
from astrbot.core.star.filter.platform_adapter_type import (
    PlatformAdapterType,
    PlatformAdapterTypeFilter,
)
from astrbot.core.star.register import register_after_message_sent as after_message_sent
from astrbot.core.star.register import register_command as command
from astrbot.core.star.register import register_regex as regex
from astrbot.core.star.register import register_llm_tool as llm_tool
"""

V340_STYLE = """from astrbot.core.star.register import (
    register_command as command,
    register_command_group as command_group,
    register_event_message_type as event_message_type,
    register_regex as regex,
    register_platform_adapter_type as platform_adapter_type,
    register_permission_type as permission_type
)

from astrbot.core.star.filter.event_message_type import EventMessageTypeFilter, EventMessageType
"""


class TestParse:
    def test_master_style(self):
        aliases, classes = parse_filter_api_exports(MASTER_STYLE)
        assert {"after_message_sent", "command", "regex", "llm_tool"} <= aliases
        assert {
            "CustomFilter",
            "EventMessageType",
            "EventMessageTypeFilter",
            "PermissionType",
            "PermissionTypeFilter",
            "PlatformAdapterType",
            "PlatformAdapterTypeFilter",
        } == classes
        # register_* import line itself must not leak into the alias set
        assert not any(a.startswith("register_") for a in aliases)

    def test_v340_style(self):
        aliases, classes = parse_filter_api_exports(V340_STYLE)
        assert aliases == {
            "command",
            "command_group",
            "event_message_type",
            "regex",
            "platform_adapter_type",
            "permission_type",
        }
        assert {"EventMessageType", "EventMessageTypeFilter"} <= classes

    def test_phantom_names_never_parse(self):
        # regression: on_keyword/on_full_match/on_regex were never part of the API
        aliases, classes = parse_filter_api_exports(MASTER_STYLE + V340_STYLE)
        assert not ({"on_keyword", "on_full_match", "on_regex"} & (aliases | classes))


class TestDriftReport:
    def test_master_exact_match_clean(self):
        aliases, classes = parse_filter_api_exports(MASTER_STYLE)
        # superset fixtures: simulate by cloning the known surface minus noise
        report = drift_report(FILTER_ATTR_KNOWN, set(), ref="master")
        # FILTER_ATTR_KNOWN itself must never report phantom against itself
        assert report["problems"] == []

    def test_master_detects_phantom(self):
        report = drift_report(FILTER_ATTR_KNOWN - {"llm_tool"}, set(), ref="master")
        assert "phantom-in-contract: llm_tool" in report["problems"]

    def test_master_detects_missing(self):
        report = drift_report(FILTER_ATTR_KNOWN | {"on_keyword"}, set(), ref="master")
        assert "missing-from-contract: on_keyword" in report["problems"]

    def test_historical_ref_allows_subset(self):
        # v3.4.0 surface ⊂ contract → subset gap is NOT drift
        aliases, classes = parse_filter_api_exports(V340_STYLE)
        report = drift_report(aliases, classes, ref="v3.4.0")
        assert report["problems"] == []
