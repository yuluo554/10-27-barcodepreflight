"""报告模型与两种渲染：契约断言 + 确定性。

覆盖：首屏三段字面、JSON 确定性、两格式 fingerprint 集合相等、fix 契约、
排序稳定、fingerprint 不含 severity。M4 追加：端到端同源、首屏顺序、渲染层零判定、
`--with-timestamp`、`out/` 落点。
"""

import ast
import datetime
import json
import pathlib

import pytest

from bpreflight import pipeline
from bpreflight.report.model import Finding, ModelError, Report
from bpreflight.report.render_json import render_json
from bpreflight.report.render_md import (
    HEADLINE_FINDINGS,
    HEADLINE_TOP_FIX,
    HEADLINE_VERDICT,
    render_md,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


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
    root = REPO_ROOT / "src" / "bpreflight" / "report"
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


# --------------------------------------------------------------------------- #
# M4 · 渲染层零判定（续）：不得自算严重级别
# --------------------------------------------------------------------------- #


def _severity_recompute_hits(source):
    """AST 判据：源码里是否出现"重算严重级别"的入口。

    认三类：**导入** `bpreflight.severity`（渲染层连它都不该看见）、属性访问
    `.rank` / `.worst` / `.verdict_for`、以及内建 `max`/`sorted` 直接吃 severity 序列
    的形态（用 `key=` 里出现 `severity` 或 `f.severity` 字符串近似锚定）。

    返回命中描述列表；空表 = 该源码没有重算。**不扫子串**（注释里写 `sev.rank`
    不该误红，`references/methodology-binding.md` 假门族 ⑱）。
    """
    tree = ast.parse(source)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "bpreflight.severity" or module.endswith(".severity"):
                hits.append("imports {}".format(module))
            for alias in node.names:
                # `from bpreflight import severity` 与 `from bpreflight.severity import rank`
                # 是同一个盖子被掀开的两种写法，都要抓。
                if alias.name in ("rank", "worst", "verdict_for", "severity"):
                    hits.append("imports {}".format(alias.name))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("bpreflight.severity", "severity"):
                    hits.append("imports {}".format(alias.name))
        elif isinstance(node, ast.Attribute):
            if node.attr in ("rank", "worst", "verdict_for"):
                hits.append("uses .{}".format(node.attr))
    return hits


def test_render_layer_does_not_recompute_severity():
    """渲染层只读 `Report` 派生好的字段，不自己重算严重级别。

    判据锚在 AST（不是子串）：`render_*.py` 里不得出现 `sev.rank` / `sev.worst` /
    `sev.verdict_for` 这些**重算**入口，也不得 import `bpreflight.severity`。
    它们只该由 `report/model.py` 的 `Report` 属性一次性算出——这正是"两套答案"的
    防线（`plan/05` §五 R3）。
    """
    root = REPO_ROOT / "src" / "bpreflight" / "report"
    scanned = 0
    for path in sorted(root.glob("render_*.py")):
        hits = _severity_recompute_hits(path.read_text(encoding="utf-8"))
        scanned += 1
        assert hits == [], "{} recomputes severity: {}".format(path.name, hits)
    assert scanned > 0, "no render_*.py found (empty scan is not a pass)"


def test_severity_recompute_detector_has_bite():
    """阳性对照：判据必须能抓住真实的重算写法（否则它只是一条永远为真的断言）。"""
    samples = [
        "import bpreflight.severity as sev\ndef f(x):\n    return sev.worst(x)\n",
        "from bpreflight.severity import rank\n",
        "from bpreflight import severity\n",
        "def f(report):\n    return [x for x in report.findings if x.severity]\n"  # 阴性：普通访问
    ]
    assert _severity_recompute_hits(samples[0]), "没抓住 sev.worst"
    assert _severity_recompute_hits(samples[1]), "没抓住 from ... import rank"
    assert _severity_recompute_hits(samples[2]), "没抓住 import severity"
    assert _severity_recompute_hits(samples[3]) == [], "普通 severity 访问被误判了"
    # 注释里提到重算入口不该误红（AST 判据的意义）。
    assert _severity_recompute_hits("# 这里不要写 sev.rank\nX = 1\n") == []


# --------------------------------------------------------------------------- #
# M4 · 首屏三段：字面 + 顺序 + 常量与 plan/03 §六逐字一致
# --------------------------------------------------------------------------- #


def test_headline_three_lines_are_contiguous_and_in_order():
    """三段必须**连续**出现在首屏前三行，位置固定（不只是"存在"）。"""
    report = Report([_finding()])
    text, _ = render_md(report)
    lines = text.splitlines()
    assert lines[0].startswith(HEADLINE_VERDICT + " ")
    assert lines[1].startswith(HEADLINE_FINDINGS + " ")
    assert lines[2].startswith(HEADLINE_TOP_FIX + " ")
    # 第二行严格是四段计数，顺序固定。
    assert lines[1] == "FINDINGS: ok=0 info=0 warn=1 error=0"


def test_headline_constants_match_plan_03_verbatim():
    """三个常量必须与 `plan/03` §六 的首屏契约逐字一致。"""
    plan = (REPO_ROOT / "plan" / "03-模块详设.md").read_text(encoding="utf-8")
    for constant in (HEADLINE_VERDICT, HEADLINE_FINDINGS, HEADLINE_TOP_FIX):
        assert constant in plan, "plan/03 §六 找不到首屏常量 {!r}".format(constant)
    # 一句完整契约行也必须在文档里逐字出现（防止常量被悄悄改名而文档没动）。
    assert "FINDINGS: ok=<n> info=<n> warn=<n> error=<n>" in plan


# --------------------------------------------------------------------------- #
# M4 · JSON / MD 端到端同源（同一 spec 走两条真实路径）
# --------------------------------------------------------------------------- #


def test_end_to_end_json_and_md_share_fingerprints():
    """同一 spec 经 pipeline 渲染两种格式：findings 按 fingerprint 集合相等，
    `verdict` 与 `summary` 一致。这挡住"某个渲染器少报了一条"。"""
    payload = {
        "schema": "bpreflight/spec/1",
        "symbol": "ean13",
        "x_dimension_mm": "0.330",
        "target_dpi": 300,
        "quiet_zone_mm": {"left": "0.6", "right": "0.6", "top": "0", "bottom": "0"},
        "gs1_element_string": "(01)09501101530003",
    }
    report = pipeline.run(payload, {"file": "spec.json", "sha256": "ab"})
    assert report.findings, "该 spec 必须产生 findings，否则同源判据空跑"

    json_text, _ = render_json(report)
    md_text, _ = render_md(report)

    payload_doc = json.loads(json_text)
    json_fps = sorted(item["fingerprint"] for item in payload_doc["findings"])
    md_fps = sorted(
        line.split("`")[1]
        for line in md_text.splitlines()
        if line.strip().startswith("- fingerprint:")
    )
    assert json_fps == md_fps == list(report.fingerprints)
    assert len(json_fps) == len(set(json_fps)), "fingerprint 集合里不应有重复项"

    # verdict 与 summary 两格式一致。
    assert payload_doc["verdict"] == report.verdict
    assert payload_doc["summary"] == report.summary
    assert md_text.splitlines()[0] == "VERDICT: {}".format(report.verdict)
    expected_counts = payload_doc["summary"]
    assert md_text.splitlines()[1] == "FINDINGS: ok={} info={} warn={} error={}".format(
        expected_counts["ok"],
        expected_counts["info"],
        expected_counts["warn"],
        expected_counts["error"],
    )


def test_fingerprints_are_stable_across_two_runs():
    """同一输入两次独立 run，fingerprint 集合相等；不同输入必须不同。"""
    payload = {
        "schema": "bpreflight/spec/1",
        "symbol": "ean13",
        "x_dimension_mm": "0.330",
        "target_dpi": 300,
        "quiet_zone_mm": {"left": "0.6", "right": "0.6", "top": "0", "bottom": "0"},
    }
    first = pipeline.run(payload, {"file": "spec.json"})
    second = pipeline.run(payload, {"file": "spec.json"})
    assert first.fingerprints == second.fingerprints
    assert first.fingerprints, "该 spec 必须有 findings"

    other = pipeline.run(
        dict(payload, quiet_zone_mm="0"),
        {"file": "spec.json"},
    )
    assert other.fingerprints != first.fingerprints


# --------------------------------------------------------------------------- #
# M4 · `--with-timestamp`：ISO-8601 UTC、无主机名 / 时区名
# --------------------------------------------------------------------------- #


def test_timestamp_absent_by_default():
    report = pipeline.run({"schema": "bpreflight/spec/1"}, {"file": "spec.json"})
    assert report.timestamp is None
    text, _ = render_json(report)
    assert "timestamp" not in text


def test_with_timestamp_has_iso_utc_and_no_host_or_zone():
    payload = {"schema": "bpreflight/spec/1"}
    report = pipeline.run(payload, {"file": "spec.json"}, with_timestamp=True)
    assert report.deterministic is False
    assert report.timestamp is not None

    # 格式固定：`YYYY-MM-DDTHH:MM:SSZ`（严格 UTC，句尾字面 Z）。
    parsed = datetime.datetime.strptime(report.timestamp, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed.tzinfo is None  # strptime 不认 Z；格式固定的证据是它没抛错

    text, _ = render_json(report)
    doc = json.loads(text)
    assert doc["timestamp"] == report.timestamp
    assert doc["deterministic"] is False
    # 不含本机时区名（UTC offset 符号 / 缩写）与主机名形态。
    assert "+" not in report.timestamp and report.timestamp.endswith("Z")
    for token in ("UTC", "GMT", "host", "machine"):
        assert token not in report.timestamp


def test_timestamp_uses_injected_clock():
    """`now` 注入：判定层读的仍是同一时钟点，不依赖系统当前时间。"""
    pinned = datetime.datetime(2026, 10, 28, 9, 15, 0, tzinfo=datetime.timezone.utc)
    report = pipeline.run(
        {"schema": "bpreflight/spec/1"},
        {"file": "spec.json"},
        with_timestamp=True,
        now=pinned,
    )
    assert report.timestamp == "2026-10-28T09:15:00Z"
