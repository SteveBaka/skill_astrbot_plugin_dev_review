# [DEV] Contract drift checks against AstrBot repo tag/master sources.
"""
Pure logic for mcp/scripts/check_contract_drift.py: parse the export surface
of astrbot/api/event/filter/__init__.py at a given ref and compare it with
contracts.FILTER_ATTR_KNOWN.

Why source files, not changelogs: API-surface changes do not reliably appear
in changelogs (e.g. the phantom on_keyword decorators never appeared in any of
200+ changelog files). Tag sources are the authoritative baseline.
"""

from __future__ import annotations

import re

from .contracts import FILTER_ATTR_KNOWN

FILTER_API_PATH = "astrbot/api/event/filter/__init__.py"
RAW_BASE = "https://raw.githubusercontent.com/AstrBotDevs/AstrBot"

_RE_ALIAS = re.compile(r"register_\w+ as (\w+)")
_RE_FROM_FILTER = re.compile(
    r"from astrbot\.core\.star\.filter\.[\w.]+ import\s*(\([^)]*\)|[^\n]*)"
)
_RE_IDENT = re.compile(r"^\w+$")


def parse_filter_api_exports(source: str) -> tuple[set[str], set[str]]:
    """Extract (decorator aliases, filter classes) from the filter API module."""
    aliases: set[str] = set()
    classes: set[str] = set()
    for m in _RE_ALIAS.finditer(source):
        aliases.add(m.group(1))
    for m in _RE_FROM_FILTER.finditer(source):
        body = m.group(1).strip().strip("()")
        for tok in body.replace(",", " ").split():
            tok = tok.strip()
            if _RE_IDENT.match(tok) and not tok.startswith("register_"):
                classes.add(tok)
    return aliases, classes


def drift_report(aliases: set[str], classes: set[str], ref: str = "master") -> dict[str, list[str]]:
    """Compare a parsed export surface with the contract table.

    ref=master expects an exact match with FILTER_ATTR_KNOWN (missing or
    unknown names both count as drift). Any other ref is a historical tag:
    its surface must be a SUBSET of the contract (later additions are fine;
    names the contract lacks are drift).
    """
    actual = aliases | classes
    missing = sorted(actual - FILTER_ATTR_KNOWN)  # contract lacks a real API
    unknown = sorted(FILTER_ATTR_KNOWN - actual)  # contract has a phantom name
    if ref == "master":
        problems = [f"missing-from-contract: {n}" for n in missing]
        problems += [f"phantom-in-contract: {n}" for n in unknown]
    else:
        problems = [f"missing-from-contract: {n}" for n in missing]
    return {"ref": [ref], "problems": problems}
