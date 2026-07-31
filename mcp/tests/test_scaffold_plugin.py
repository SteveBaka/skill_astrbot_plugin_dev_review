"""Scaffold invariant: every SCAFFOLD_TYPE fresh tree → review error=0."""
from __future__ import annotations

import json

import pytest

from runtime.contracts import SCAFFOLD_TYPES, validate_plugin_name, slug_to_class_name
from runtime.review_static import review_adapter_directory, review_plugin_directory
from runtime.scaffold_plugin import scaffold_plugin


class TestContracts:
    def test_plugin_name_validation(self):
        assert validate_plugin_name("astrbot_plugin_hello") is None
        assert validate_plugin_name("Hello") is not None

    def test_class_name(self):
        assert slug_to_class_name("astrbot_plugin_foo_bar") == "FooBarPlugin"


class TestScaffoldInvariant:
    @pytest.mark.parametrize("ptype", [t for t in SCAFFOLD_TYPES if t != "adapter"])
    def test_star_scaffold_review_error_zero(self, tmp_path, ptype):
        name = f"astrbot_plugin_scaf_{ptype}"
        result = scaffold_plugin(
            name,
            "ScaffoldTestAuthor",
            plugin_type=ptype,
            output_dir=str(tmp_path),
            command="ping",
        )
        assert result["ok"] is True, result
        assert result["review"]["counts"].get("error", 0) == 0
        report = review_plugin_directory(result["path"])
        errors = [f for f in report.findings if f.severity == "error"]
        assert errors == [], [e.to_dict() for e in errors]

    def test_adapter_frame_review_error_zero(self, tmp_path):
        result = scaffold_plugin(
            "demoplat",
            "ScaffoldTestAuthor",
            plugin_type="adapter",
            output_dir=str(tmp_path),
        )
        assert result["ok"] is True, result
        assert result.get("framework_only") is True
        assert result["review"]["counts"].get("error", 0) == 0
        report = review_adapter_directory(result["path"])
        errors = [f for f in report.findings if f.severity == "error"]
        assert errors == [], [e.to_dict() for e in errors]

    def test_adapter_fix06_detects_reserved_assign(self, tmp_path):
        # hand-broken adapter: self.client = ...
        d = tmp_path / "astrbot_plugin_badadapt"
        d.mkdir()
        (d / "metadata.yaml").write_text(
            "name: astrbot_plugin_badadapt\ndesc: x\nversion: 0.1.0\nauthor: t\n",
            encoding="utf-8",
        )
        (d / "requirements.txt").write_text("#\n", encoding="utf-8")
        (d / "main.py").write_text(
            '''import asyncio
from astrbot.api.platform import Platform, PlatformMetadata
from astrbot.core.platform.register import register_platform_adapter
from astrbot.api.event import MessageChain

@register_platform_adapter("badadapt", "bad")
class BadAdapt(Platform):
    def __init__(self, platform_config, platform_settings, event_queue):
        super().__init__(platform_config, event_queue)
        self.client = None  # FIX-06

    def meta(self):
        return PlatformMetadata(name="badadapt", description="x", id="badadapt")

    async def run(self):
        await asyncio.sleep(1)

    async def send_by_session(self, session, message_chain: MessageChain):
        pass
''',
            encoding="utf-8",
        )
        report = review_adapter_directory(d)
        rules = [f.rule for f in report.findings if f.severity == "error"]
        assert "FIX-06" in rules

    def test_adapter_fix06_redundant_core_keys_are_warning(self, tmp_path):
        """Official register injects id/enable — re-listing is warning, not load-break."""
        d = tmp_path / "astrbot_plugin_badcfg"
        d.mkdir()
        (d / "metadata.yaml").write_text(
            "name: astrbot_plugin_badcfg\ndesc: x\nversion: 0.1.0\nauthor: t\n",
            encoding="utf-8",
        )
        (d / "requirements.txt").write_text("#\n", encoding="utf-8")
        (d / "main.py").write_text(
            '''import asyncio
from astrbot.api.platform import Platform, PlatformMetadata
from astrbot.core.platform.register import register_platform_adapter
from astrbot.api.event import MessageChain

@register_platform_adapter(
    "badcfg",
    "bad",
    default_config_tmpl={"id": "x", "enable": True, "token": ""},
)
class BadCfg(Platform):
    def __init__(self, platform_config, platform_settings, event_queue):
        super().__init__(platform_config, event_queue)

    def meta(self):
        return PlatformMetadata(name="badcfg", description="x", id="badcfg")

    async def run(self):
        await asyncio.sleep(1)

    async def send_by_session(self, session, message_chain: MessageChain):
        pass
''',
            encoding="utf-8",
        )
        report = review_adapter_directory(d)
        warns = [
            f
            for f in report.findings
            if f.rule == "FIX-06" and f.severity == "warning"
        ]
        assert warns, report.findings
        assert report.ok  # warnings do not fail adapter profile ok

    def test_adapter_fix06_conf_schema_file(self, tmp_path):
        d = tmp_path / "astrbot_plugin_badschema"
        d.mkdir()
        (d / "metadata.yaml").write_text(
            "name: astrbot_plugin_badschema\ndesc: x\nversion: 0.1.0\nauthor: t\n",
            encoding="utf-8",
        )
        (d / "requirements.txt").write_text("#\n", encoding="utf-8")
        (d / "_conf_schema.json").write_text('{"token": {"type": "string"}}\n')
        (d / "main.py").write_text(
            '''import asyncio
from astrbot.api.platform import Platform, PlatformMetadata
from astrbot.core.platform.register import register_platform_adapter
from astrbot.api.event import MessageChain

@register_platform_adapter("badschema", "bad", default_config_tmpl={"token": ""})
class BadSchema(Platform):
    def __init__(self, platform_config, platform_settings, event_queue):
        super().__init__(platform_config, event_queue)

    def meta(self):
        return PlatformMetadata(name="badschema", description="x", id="badschema")

    async def run(self):
        await asyncio.sleep(1)

    async def send_by_session(self, session, message_chain: MessageChain):
        pass
''',
            encoding="utf-8",
        )
        report = review_adapter_directory(d)
        files = [f.file for f in report.findings if f.rule == "FIX-06"]
        assert "_conf_schema.json" in files

    def test_mcp_json_entry(self, tmp_path):
        from runtime.scaffold_plugin import astrbot_scaffold_plugin

        raw = astrbot_scaffold_plugin(
            "astrbot_plugin_json_entry",
            "Author",
            plugin_type="hook",
            output_dir=str(tmp_path),
        )
        data = json.loads(raw)
        assert data["ok"] is True

    def test_bad_name_rejected(self, tmp_path):
        r = scaffold_plugin("BadName", "A", output_dir=str(tmp_path))
        assert r["ok"] is False
        assert r["error_kind"] == "bad_name"
