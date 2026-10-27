"""M3 颜色：两项判据**不合并**，以及"红条 + 红光"与"红条 + 白光"必须分开锁。

§8.4 的两项是：

  1. 亮度对比（`insufficient_contrast` / `low_contrast`）—— 与照明无关，永远判；
  2. 窄带波长通道反射率塌陷（`wavelength_reflectance_collapse`）—— 只在照明建模到
     某个通道时判（`red`），白光不判。

本文件的核心断言是**同一对颜色在两个照明下给出不同 id**：`#C8102E` + 白光 → 亮度项
`ok`（5.88:1）；`#C8102E` + 红光 → `wavelength_reflectance_collapse`。把两者合成一条
"对比度不足"就会丢掉这个区别（`plan/01` §M3 明列的常见误判）。

用例的期望值来自 `color_cases.json`（数据），测试**重算**亮度与通道差再比，不抄结论。
"""

import json
from decimal import Decimal

import pytest

from bpreflight import thresholds
from bpreflight.print import color


@pytest.fixture(scope="module")
def book():
    return thresholds.load_book()


def _ids(findings):
    return [finding.id for finding in findings]


def _run(book, bar, space, illumination):
    return color.check(book, bar, space, illumination)


# --------------------------------------------------------------------------- #
# 1. 亮度项（与照明无关）
# --------------------------------------------------------------------------- #


def test_relative_luminance_matches_the_documented_value(book):
    """`#C8102E` 的相对亮度必须约等于 §8.4 记录的 0.1285（独立复算，不读结论）。"""
    luminance = color.relative_luminance(color.parse_color("#C8102E"))
    assert round(float(luminance), 4) == 0.1285


def test_documented_contrast_ratio_is_reproducible(book):
    """`#C8102E` 对白底 ≈ 5.88 —— §8.4 的实算值，逐位复核（容许 0.01 的取整）。"""
    ratio = color.contrast_ratio(color.parse_color("#C8102E"),
                                 color.parse_color("#FFFFFF"))
    assert abs(float(ratio) - 5.88) < 0.01, float(ratio)


def test_insufficient_contrast_is_an_error_with_a_ratio_target(book):
    findings = _run(book, "#999999", "#FFFFFF", "white")
    assert _ids(findings) == ["insufficient_contrast"]
    finding = findings[0]
    assert finding.severity == "error"
    assert finding.threshold_status == "not-applicable"
    assert finding.fix["min_delta"]


def test_low_contrast_is_a_warn(book):
    findings = _run(book, "#808080", "#FFFFFF", "white")
    assert _ids(findings) == ["low_contrast"]
    assert findings[0].severity == "warn"


def test_borderline_contrast_above_the_warn_floor_is_clean(book):
    findings = _run(book, "#767676", "#FFFFFF", "white")
    assert findings == []


def test_contrast_categories_are_mutually_exclusive(book):
    """error 档不再叠加一条 warn：一条 finding，不是两条。"""
    for bar in ("#999999", "#808080", "#000000"):
        findings = _run(book, bar, "#FFFFFF", "white")
        ids = _ids(findings)
        assert len(ids) == len(set(ids)), ids
        assert not ("insufficient_contrast" in ids and "low_contrast" in ids)


# --------------------------------------------------------------------------- #
# 2. 波长项 —— 与亮度项不合并
# --------------------------------------------------------------------------- #


def test_red_bars_under_red_light_collapse(book):
    """红条 + 红光：唯一输出 `wavelength_reflectance_collapse`，且不夹带低对比。"""
    findings = _run(book, "#C8102E", "#FFFFFF", "red")
    assert _ids(findings) == ["wavelength_reflectance_collapse"]
    assert findings[0].severity == "error"
    assert findings[0].threshold_status == "not-applicable"


def test_red_bars_under_white_light_only_judge_luminance(book):
    """红条 + 白光：亮度 5.88:1 → 干净；**不**跑波长项（白光不是窄带）。"""
    findings = _run(book, "#C8102E", "#FFFFFF", "white")
    assert findings == []


def test_the_two_probes_are_not_merged(book):
    """同一个 bar 在两种照明下给出**不同**的 id —— 合并判据就会抹掉这层区别。"""
    red_light = _ids(_run(book, "#C8102E", "#FFFFFF", "red"))
    white_light = _ids(_run(book, "#C8102E", "#FFFFFF", "white"))
    assert red_light == ["wavelength_reflectance_collapse"]
    assert white_light == []
    assert set(red_light) != set(white_light)


def test_both_probes_can_fire_together_and_neither_suppresses_the_other(book):
    """橙条 + 红光：亮度不足**且**通道差不足 → 两条并存，互不压制。

    `#C86E00` 对白底 3.69:1（落在 [3.0, 4.5) → low_contrast），红通道差 0.216
    （< delta_min → collapse）。两条判据各自独立成立，谁都不许把另一条压掉。
    """
    findings = _run(book, "#C86E00", "#FFFFFF", "red")
    ids = _ids(findings)
    assert ids == ["low_contrast", "wavelength_reflectance_collapse"], ids


def test_channel_delta_is_recomputed_from_the_colour(book):
    """通道差由 8-bit 值直接算：`#C8102E` 的红通道 200/255 vs 255/255。"""
    rule = book.engineering("wavelength_reflectance_delta_min")
    bar = color.parse_color("#C8102E")
    space = color.parse_color("#FFFFFF")
    delta = abs(color.channel_reflectance(space, "red")
                - color.channel_reflectance(bar, "red"))
    assert delta == (Decimal(255) - Decimal(200)) / Decimal(255)
    assert delta < Decimal(rule["value"])


def test_black_bars_under_red_light_are_fine(book):
    """黑条吸全通道：红通道差 = 1.0 → 不塌陷。"""
    assert _run(book, "#000000", "#FFFFFF", "red") == []


# --------------------------------------------------------------------------- #
# 3. 未建模面（§8.9 G5）
# --------------------------------------------------------------------------- #


def test_metallic_ink_is_unmodelled_not_a_pass(book):
    findings = _run(book, "metallic", "#FFFFFF", "white")
    assert _ids(findings) == ["surface_effect_unmodeled"]
    assert findings[0].severity == "info"
    assert findings[0].fix is None


def test_infrared_light_is_unmodelled(book):
    findings = _run(book, "#000000", "#FFFFFF", "ir")
    assert _ids(findings) == ["surface_effect_unmodeled"]
    assert findings[0].severity == "info"


def test_unknown_illumination_is_unmodelled_not_an_install_error(book):
    """表里没有的照明是**用户 spec 的问题**（info），不是 exit 3。"""
    findings = _run(book, "#000000", "#FFFFFF", "uv")
    assert _ids(findings) == ["surface_effect_unmodeled"]


def test_unmodelled_surface_never_yields_a_contrast_verdict(book):
    """G5 的纪律：给了 info 就不能同时给 pass 或 fail（不得用 ok 表示不知道）。"""
    findings = _run(book, "metallic", "#FFFFFF", "white")
    assert not [f for f in findings if f.id in ("insufficient_contrast", "low_contrast")]


# --------------------------------------------------------------------------- #
# 4. 数据驱动：`color_cases.json` 的用例逐条重跑
# --------------------------------------------------------------------------- #


def test_every_data_case_reproduces(book):
    """`color_cases.json` 的每条用例都由判定重算一遍（期望值来自数据，不抄报告）。"""
    for case in book.color_cases["cases"]:
        findings = color.check(
            book, case["bar_color"], case["space_color"], case["illumination"]
        )
        assert _ids(findings) == case["expected"], case["name"]


def test_cases_cover_both_probes_and_the_unmodelled_channel(book):
    """用例集不许退化成"只测一种颜色"——覆盖度本身要可断言。"""
    ids = set()
    flows = set()
    for case in book.color_cases["cases"]:
        flows.add(case["illumination"])
        ids.update(case["expected"])
    for expected in (
        "wavelength_reflectance_collapse",
        "insufficient_contrast",
        "low_contrast",
        "surface_effect_unmodeled",
    ):
        assert expected in ids, expected
    assert {"white", "red", "ir"} <= flows


def test_illumination_table_has_no_status_fields(book):
    """工程判据表不带 status（K8）：否则"未核降级"会漏进颜色项。"""
    for name, entry in book.color_cases["illuminations"].items():
        assert "status" not in entry, name
        assert "verified_at" not in entry, name
        assert isinstance(entry["modelled"], bool), name
