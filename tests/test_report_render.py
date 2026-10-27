"""报告模型与两种渲染：契约断言 + 确定性。

覆盖：首屏三段字面、JSON 确定性、两格式 fingerprint 集合相等、fix 契约、
排序稳定、fingerprint 不含 severity。
"""

import json

import pytest

from bpreflight.report.model import Finding, ModelError, Report
from bpreflight.report.render_json import render_json
from bpreflight.report.render_md import (
    HEADLINE_FINDINGS,
    HEADLINE_TOP_FIX,
    HEADLINE_VERDICT,
    render_md,
)


def _finding(**overrides):
    base = dict(
        id="quiet_zone_insufficient",
        module="M3",
        severity="warn",
        observed="1.818",
        target="quiet_zone.left",
        ai_position=-1,
        threshold="7",
        threshold_status="unverified",
        basis="gen-spec",
        evidence={"kind": "official-source", "ref": "placeholder", "quote": "n/a"},
        fix={
            "kind": "increase_quiet_zone",
            "to": "2.310",
            "unit": "mm",
            "rationale": "modules_min x x_dimension",
        },
    )
    base.update(overrides)
    return Finding(**base)


def test_report_verdict_from_findings():
    assert Report([_finding(severity="warn")]).verdict == "warn"
    assert Report([_finding(severity="error")]).verdict == "fail"
    assert Report([]).verdict == "pass"


def test_findings_sorted_by_module_position_id():
    a = _finding(id="z_id", module="M1")
    b = _finding(id="a_id", module="M1")
    c = _finding(id="a_id", module="M0")
    report = Report([a, b, c])
    assert [f.id for f in report.findings] == ["a_id", "a_id", "z_id"]
    assert [f.module for f in report.findings] == ["M0", "M1", "M1"]


def test_fingerprint_ignores_severity_and_threshold_status():
    """阈值状态一改 severity 就变；fingerprint 含它会让跨 run diff 全是噪音。"""
    warn = _finding(severity="warn", threshold_status="unverified")
    error = _finding(severity="error", threshold_status="verified")
    assert warn.fingerprint == error.fingerprint


def test_fingerprint_changes_with_target():
    assert _finding(target="quiet_zone.left").fingerprint != _finding(
        target="quiet_zone.right"
    ).fingerprint


def test_finding_is_immutable():
    finding = _finding()
    with pytest.raises(AttributeError):
        finding.severity = "error"


def test_warn_without_fix_is_rejected():
    with pytest.raises(ModelError):
        _finding(fix=None)


def test_fix_without_target_value_is_rejected():
    """决策 D9："请检查你的条码" 不算 fix。"""
    with pytest.raises(ModelError):
        _finding(fix={"kind": "check_your_barcode", "rationale": "n/a"})


def test_fix_with_min_delta_is_accepted():
    finding = _finding(
        fix={"kind": "increase_dpi", "min_delta": "40", "unit": "dpi", "rationale": "n/a"}
    )
    assert finding.fix["min_delta"] == "40"


def test_evidence_kind_is_enforced():
    with pytest.raises(ModelError):
        _finding(evidence={"kind": "made-up", "ref": "x", "quote": "y"})


def test_info_needs_no_fix():
    """info 级不强制 fix（例如 `dd00_last_day_of_month`）。"""
    finding = _finding(
        id="dd00_last_day_of_month",
        severity="info",
        fix=None,
        basis="official-dictionary",
    )
    assert finding.fix is None


def test_markdown_headline_three_lines_are_literal():
    report = Report([_finding()])
    text, _ = render_md(report)
    lines = text.splitlines()
    assert lines[0] == "VERDICT: warn"
    assert lines[1] == "FINDINGS: ok=0 info=0 warn=1 error=0"
    assert lines[2].startswith("TOP FIX: increase_quiet_zone")


def test_markdown_top_fix_none_when_no_actionable():
    report = Report([])
    text, _ = render_md(report)
    assert "TOP FIX: none" in text


def test_headline_constants_match_contract():
    assert HEADLINE_VERDICT == "VERDICT:"
    assert HEADLINE_FINDINGS == "FINDINGS:"
    assert HEADLINE_TOP_FIX == "TOP FIX:"


def test_json_is_deterministic_across_two_runs():
    report = Report([_finding()], input_info={"file": "spec.json", "sha256": "ab"})
    first, _ = render_json(report)
    second, _ = render_json(Report([_finding()], input_info={"file": "spec.json", "sha256": "ab"}))
    assert first == second
    assert first.endswith("\n")
    assert not first.endswith("\n\n")


def test_two_formats_share_the_same_fingerprints():
    """两格式同源：`findings` 按 fingerprint 必须完全相等（不许多报/漏报）。"""
    report = Report([_finding(), _finding(id="other", target="quiet_zone.right")])
    json_text, _ = render_json(report)
    payload = json.loads(json_text)
    json_fps = sorted(item["fingerprint"] for item in payload["findings"])
    assert json_fps == report.fingerprints

    md_text, _ = render_md(report)
    md_fps = sorted(
        line.split("`")[1]
        for line in md_text.splitlines()
        if line.strip().startswith("- fingerprint:")
    )
    assert md_fps == json_fps


def test_json_has_no_timestamp_by_default():
    """默认不读时钟：报告里没有 timestamp 字段，`deterministic` 为 true。"""
    report = Report([_finding()])
    text, _ = render_json(report)
    payload = json.loads(text)
    assert payload["deterministic"] is True
    assert "timestamp" not in payload
    assert "timestamp" not in text


def test_render_layer_has_no_judgement_imports():
    """渲染层零判定：只准依赖 `report.model`，不准 import 判定模块（AST 守门）。"""
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "bpreflight" / "report"
    forbidden = {"bpreflight.gs1", "bpreflight.symbols", "bpreflight.print", "bpreflight.oracle"}
    scanned = 0
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        scanned += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden, "{} imports {}".format(path.name, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module not in forbidden, "{} imports {}".format(
                        path.name, node.module
                    )
    assert scanned > 0, "render layer scan found no files (empty scan is not a pass)"
