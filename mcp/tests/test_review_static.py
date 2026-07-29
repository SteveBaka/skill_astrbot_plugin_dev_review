"""Unit tests for runtime.review_static — AST checks mapped to FIX rules.

Primary fixture: the real example plugin plugin-types/type2-session-waiter
(must be finding-free at error level). Synthetic bad plugins cover each rule.
"""
from __future__ import annotations

from runtime.review_static import review_plugin_directory


def _write_plugin(tmp_path, main_src: str, meta: str | None = None, req: str = ""):
    (tmp_path / "metadata.yaml").write_text(
        meta
        if meta is not None
        else "name: astrbot_plugin_t\ndesc: test\nversion: 1.0.0\nauthor: t\n"
    )
    (tmp_path / "main.py").write_text(main_src)
    if req:
        (tmp_path / "requirements.txt").write_text(req)
    return tmp_path


def _rules(report, severity=None):
    return [
        f.rule for f in report.findings if severity is None or f.severity == severity
    ]


# ── real example plugin must pass at error level ───────────────


class TestFixturePluginClean:
    def test_type2_no_errors(self, fixture_plugin_dir):
        report = review_plugin_directory(fixture_plugin_dir)
        assert report.files_checked >= 1
        errors = [f for f in report.findings if f.severity == "error"]
        assert errors == [], [f.to_dict() for f in errors]
        assert report.ok


# ── import rules ───────────────────────────────────────────────


class TestImportRules:
    def test_fix00_wrong_logger_module(self, tmp_path):
        root = _write_plugin(tmp_path, "from astrbot.api.logger import logger\n")
        report = review_plugin_directory(root)
        assert "FIX-00" in _rules(report, "error")
        assert not report.ok

    def test_fix00_wrong_symbol_from_api(self, tmp_path):
        root = _write_plugin(tmp_path, "from astrbot.api import filter, Star\n")
        report = review_plugin_directory(root)
        assert _rules(report, "error").count("FIX-00") == 2

    def test_fix04_requests_import(self, tmp_path):
        for src in ("import requests\n", "from requests import get\n"):
            root = _write_plugin(tmp_path, src)
            report = review_plugin_directory(root)
            assert "FIX-04" in _rules(report, "error")

    def test_fix23_unused_import(self, tmp_path):
        root = _write_plugin(tmp_path, "import os\nimport json\nprint(json.dumps({}))\n")
        report = review_plugin_directory(root)
        info = [f for f in report.findings if f.rule == "FIX-23"]
        assert len(info) == 1 and "os" in info[0].message
        assert report.ok  # info does not block

    def test_correct_imports_clean(self, tmp_path):
        root = _write_plugin(
            tmp_path,
            "from astrbot.api import logger, AstrBotConfig\n"
            "from astrbot.api.event import filter, AstrMessageEvent\n"
            "logger.info(str(AstrBotConfig))\n"
            "print(filter, AstrMessageEvent)\n",
        )
        report = review_plugin_directory(root)
        assert _rules(report, "error") == []


# ── AST structure rules ────────────────────────────────────────


STAR_OK = '''
from astrbot.api.star import Star, Context

class MyPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config
'''

STAR_NO_SUPER = '''
from astrbot.api.star import Star, Context

class MyPlugin(Star):
    def __init__(self, context: Context):
        self.context = context
'''


class TestStructureRules:
    def test_fix01_missing_super(self, tmp_path):
        report = review_plugin_directory(_write_plugin(tmp_path, STAR_NO_SUPER))
        assert "FIX-01" in _rules(report, "error")

    def test_star_ok_clean(self, tmp_path):
        report = review_plugin_directory(_write_plugin(tmp_path, STAR_OK))
        assert "FIX-01" not in _rules(report)

    def test_fix20_dataclass_mutable_default(self, tmp_path):
        src = (
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class P:\n"
            "    params: dict = {}\n"
        )
        report = review_plugin_directory(_write_plugin(tmp_path, src))
        assert "FIX-20" in _rules(report, "error")

    def test_fix21_deprecated_filter(self, tmp_path):
        src = (
            "from astrbot.api.event import filter\n"
            "@filter.on_keyword('hi')\n"
            "async def h(self, event):\n"
            "    pass\n"
        )
        report = review_plugin_directory(_write_plugin(tmp_path, src))
        assert "FIX-21" in _rules(report, "error")

    def test_fix17_command_missing_docstring(self, tmp_path):
        src = (
            "from astrbot.api.event import filter\n"
            "class T:\n"
            "    @filter.command('hello')\n"
            "    async def hello(self, event):\n"
            "        return 1\n"
        )
        report = review_plugin_directory(_write_plugin(tmp_path, src))
        assert "FIX-17" in _rules(report, "warning")

    def test_fix02_extra_handler_params(self, tmp_path):
        src = (
            "from astrbot.api.event import filter\n"
            "class T:\n"
            "    @filter.command('echo')\n"
            "    async def echo(self, event, text):\n"
            "        '''echo'''\n"
            "        return text\n"
        )
        report = review_plugin_directory(_write_plugin(tmp_path, src))
        assert "FIX-02" in _rules(report, "warning")

    def test_fix27_startools_outside_star(self, tmp_path):
        src = (
            "from astrbot.api.star import StarTools\n"
            "class Service:\n"
            "    def d(self):\n"
            "        return StarTools.get_data_dir('x')\n"
        )
        report = review_plugin_directory(_write_plugin(tmp_path, src))
        assert "FIX-27" in _rules(report, "warning")

    def test_syntax_error_reported(self, tmp_path):
        report = review_plugin_directory(_write_plugin(tmp_path, "def broken(\n"))
        assert "SYNTAX" in _rules(report, "error")


# ── metadata / requirements ────────────────────────────────────


class TestMetadataRules:
    def test_missing_fields(self, tmp_path):
        root = _write_plugin(tmp_path, "x = 1\n", meta="name: astrbot_plugin_x\n")
        report = review_plugin_directory(root)
        # desc/version/author missing
        assert _rules(report, "error").count("META-02") == 3

    def test_naming_prefix(self, tmp_path):
        root = _write_plugin(
            tmp_path, "x = 1\n",
            meta="name: myplugin\ndesc: d\nversion: 1.0.0\nauthor: a\n",
        )
        report = review_plugin_directory(root)
        assert "META-03" in _rules(report, "warning")

    def test_astrbot_version_v_prefix(self, tmp_path):
        root = _write_plugin(
            tmp_path, "x = 1\n",
            meta="name: astrbot_plugin_x\ndesc: d\nversion: 1.0.0\nauthor: a\nastrbot_version: '>=v4.16'\n",
        )
        report = review_plugin_directory(root)
        assert "META-04" in _rules(report, "warning")


class TestRequirementsRules:
    def test_req01_undeclared_third_party(self, tmp_path):
        root = _write_plugin(tmp_path, "import aiofiles\nprint(aiofiles)\n")
        report = review_plugin_directory(root)
        assert "REQ-01" in _rules(report, "warning")

    def test_declared_dep_clean(self, tmp_path):
        root = _write_plugin(
            tmp_path, "import aiofiles\nprint(aiofiles)\n", req="aiofiles>=23.0\n"
        )
        report = review_plugin_directory(root)
        assert "REQ-01" not in _rules(report)

    def test_stdlib_and_astrbot_ignored(self, tmp_path):
        root = _write_plugin(
            tmp_path,
            "import os, json, asyncio\nfrom astrbot.api import logger\n"
            "print(os, json, asyncio, logger)\n",
        )
        report = review_plugin_directory(root)
        assert "REQ-01" not in _rules(report)


class TestNamespaceRule:
    def test_fix26_generic_pkg_without_guard(self, tmp_path):
        root = _write_plugin(tmp_path, "from services.api import x\nprint(x)\n")
        pkg = root / "services"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "api.py").write_text("x = 1\n")
        report = review_plugin_directory(root)
        assert "FIX-26" in _rules(report, "warning")

    def test_guarded_is_clean(self, tmp_path):
        root = _write_plugin(
            tmp_path,
            "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\n"
            "from services.api import x\nprint(x)\n",
        )
        pkg = root / "services"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "api.py").write_text("x = 1\n")
        report = review_plugin_directory(root)
        assert "FIX-26" not in _rules(report)


class TestEntryGates:
    def test_not_a_dir(self, tmp_path):
        report = review_plugin_directory(tmp_path / "nope")
        assert not report.ok and report.error

    def test_no_main(self, tmp_path):
        (tmp_path / "metadata.yaml").write_text("name: x\n")
        report = review_plugin_directory(tmp_path)
        assert not report.ok and "main.py" in report.error
