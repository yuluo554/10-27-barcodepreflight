"""`fix` 是必填契约，不是建议（决策 D9）。

`Finding.__init__` 在构造期就拒收"warn/error 无 fix"与"fix 无 to/min_delta"，
所以这条测试做两件事：

  1. **端到端**：用一组覆盖 M1/M2/M3 全部判定分支的 spec 跑 pipeline，逐条断言
     每个 `warn`/`error` 都有可执行 fix（含 `to` 或 `min_delta`，且有 `unit`）。
  2. **反向**：构造期确实会拒收空话（"请检查你的条码"）——否则第 1 条可能只是
     "没人产过 warn"，而不是"产了也必然合规"。

第 1 条的覆盖面由**断言统计**保证：如果某次改动让某类 finding 不再被触发，
`test_the_corpus_still_exercises_every_m3_branch` 会变红，而不是静静少测一块。
"""

import pytest

from bpreflight import pipeline
from bpreflight import severity as sev
from bpreflight import thresholds
from bpreflight.print import audit, color, common
from bpreflight.report.model import Finding, ModelError
from bpreflight.symbols import profiles

BASE = {
    "schema": "bpreflight/spec/1",
    "symbol": "ean13",
    "x_dimension_mm": "0.330",
    "target_dpi": 203,
    "quiet_zone_mm": "5",
    "bar_height_mm": "22.85",
    "bar_color": "#000000",
    "space_color": "#FFFFFF",
    "illumination": "white",
    "identifier": "4006381333931",
}


def _payload(**overrides):
    payload = dict(BASE)
    payload.update(overrides)
    return payload


#: 覆盖 M1/M2/M3 各分支的语料。每条都**故意**触发一个 warn 或 error。
CORPUS = [
    ("M1 校验位", _payload(identifier="4006381333932")),
    ("M1 日期 DD=00 反例", _payload(identifier=None, gs1_element_string="(17)251301")),
    ("M1 缺 req", _payload(identifier=None, gs1_element_string="(10)BATCH")),
    ("M1 ex 互斥", _payload(identifier=None, gs1_element_string="(01)09501101530003(255)X")),
    ("M2 长度", _payload(symbol="upca")),
    ("M2 字符集", _payload(symbol="code39", identifier="abc")),
    ("M3 零静区", _payload(quiet_zone_mm="0")),
    ("M3 静区不足", _payload(quiet_zone_mm="0.6")),
    ("M3 静区贴近", _payload(quiet_zone_mm="3.75", target_dpi=300)),
    ("M3 放大率下限", _payload(x_dimension_mm="0.2639", target_dpi=300)),
    ("M3 放大率上限", _payload(x_dimension_mm="0.6601", target_dpi=300)),
    ("M3 DPI 高风险", _payload(target_dpi=100)),
    ("M3 DPI 风险", _payload(target_dpi=120)),
    ("M3 条高", _payload(bar_height_mm="10.0", target_dpi=300)),
    ("M3 对比度 error", _payload(bar_color="#999999", target_dpi=300)),
    ("M3 对比度 warn", _payload(bar_color="#808080", target_dpi=300)),
    ("M3 波长塌陷", _payload(bar_color="#C8102E", illumination="red", target_dpi=300)),
    ("M3 缺参", {"schema": "bpreflight/spec/1", "symbol": "ean13", "target_dpi": 300}),
]


def test_every_warn_and_error_carries_an_actionable_fix():
    """全语料：每个 warn/error 的 fix 都必须有 `to` 或 `min_delta`，且带 `unit`。"""
    checked = 0
    for label, payload in CORPUS:
        report = pipeline.run(payload, {"file": "spec.json"})
        for finding in report.findings:
            if finding.severity not in (sev.WARN, sev.ERROR):
                continue
            checked += 1
            fix = finding.fix
            assert fix, "{} / {} 是 {} 却没有 fix".format(label, finding.id, finding.severity)
            assert fix.get("kind"), "{} / {} 的 fix 缺 kind".format(label, finding.id)
            assert fix.get("unit"), "{} / {} 的 fix 缺 unit".format(label, finding.id)
            has_target = fix.get("to") is not None
            has_delta = fix.get("min_delta") is not None
            assert has_target or has_delta, "{} / {} 的 fix 既无 to 也无 min_delta".format(
                label, finding.id
            )
    assert checked >= len(CORPUS), (
        "语料只产出 {} 条 warn/error（期望 >= {}）—— 有分支没被触发，"
        "这条测试正在空跑".format(checked, len(CORPUS))
    )


def test_the_corpus_still_exercises_every_m3_branch():
    """M3 的每条 id 都至少被语料触发一次（防止分支悄悄失联）。"""
    seen = set()
    for _, payload in CORPUS:
        report = pipeline.run(payload, {"file": "spec.json"})
        seen.update(f.id for f in report.findings if f.module == "M3")
    expected = {
        "quiet_zone_absent",
        "quiet_zone_insufficient",
        "quiet_zone_marginal",
        "magnification_below_range",
        "magnification_above_range",
        "raster_alias_high_risk",
        "raster_alias_risk",
        "bar_height_insufficient",
        "insufficient_contrast",
        "low_contrast",
        "wavelength_reflectance_collapse",
        "input_incomplete",
    }
    assert expected - seen == set(), "这些 M3 分支没被语料触发: {}".format(
        sorted(expected - seen)
    )


def test_fix_target_values_are_recomputable():
    """`fix.to` 必须能从输入与数据独立复算（不是抄一个字符串）。"""
    book = thresholds.load_book()
    profiles_book = profiles.load()

    # 静区：to = modules_min x x_dimension
    result = audit.assess(book, profiles_book, _payload(quiet_zone_mm="0.6"))
    finding = [f for f in result.findings if f.id == "quiet_zone_insufficient"][0]
    left = book.quiet_zone_entry("ean13", "left")
    assert finding.fix["to"] == common.fixed(left["modules_min"] * 0.330)

    # 条高：to = modules_min x x_dimension
    result = audit.assess(book, profiles_book, _payload(bar_height_mm="10.0", target_dpi=300))
    finding = [f for f in result.findings if f.id == "bar_height_insufficient"][0]
    entry = book.gen_spec_entry("bar_height_modules_min_ean13")
    assert finding.fix["to"] == common.fixed(float(entry["value"]) * 0.330)

    # DPI：to 是"刚好越过 warn 门限"的整数 DPI
    result = audit.assess(book, profiles_book, _payload(target_dpi=100))
    finding = [f for f in result.findings if f.id == "raster_alias_high_risk"][0]
    from decimal import Decimal

    needed = Decimal(finding.fix["to"])
    dots = Decimal("0.330") / Decimal(book.mm_per_inch) * needed
    assert dots >= Decimal(book.engineering("dots_per_module")["warn_below"])
    assert dots - Decimal("0.330") / Decimal(book.mm_per_inch) < Decimal(
        book.engineering("dots_per_module")["warn_below"]
    ), "fix.to 不是最小可行 DPI（多抬了一格）"


def test_contrast_fix_delta_reaches_the_threshold():
    """亮度项的 min_delta 必须恰好补到 `warn_below`，不是随便一个数。"""
    book = thresholds.load_book()
    findings = color.check(book, "#999999", "#FFFFFF", "white")
    finding = findings[0]
    ratio = color.contrast_ratio(color.parse_color("#999999"), color.parse_color("#FFFFFF"))
    warn_below = book.engineering("contrast_ratio")["warn_below"]
    assert finding.fix["min_delta"] == common.fixed(float(warn_below) - float(ratio))


# --------------------------------------------------------------------------- #
# 反向：构造期确实会拒收空话
# --------------------------------------------------------------------------- #


def _evidence():
    return {"kind": "engineering-heuristic", "ref": "x", "quote": "y"}


def test_empty_fix_is_rejected_at_construction():
    with pytest.raises(ModelError):
        Finding(
            id="demo", module="M3", severity="warn", observed="x", target="t",
            evidence=_evidence(), fix=None,
        )


def test_vague_fix_is_rejected_at_construction():
    """决策 D9 的原话：`{"fix": "请检查你的条码"}` 视为缺陷。"""
    with pytest.raises(ModelError):
        Finding(
            id="demo", module="M3", severity="error", observed="x", target="t",
            evidence=_evidence(), fix={"kind": "check_your_barcode", "rationale": "n/a"},
        )


def test_info_may_omit_fix():
    finding = Finding(
        id="surface_effect_unmodeled", module="M3", severity="info", observed="x",
        target="color", evidence=_evidence(), fix=None,
    )
    assert finding.fix is None
