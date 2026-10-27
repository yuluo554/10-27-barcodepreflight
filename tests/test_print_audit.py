"""M3 印刷层：五项检查 + 边界值逐条 + 缺参拒判 + 三态降级。

判据分五组：

  1. **静区三档**——结构档（零静区）恒 error 且与阈值状态无关；阈值档随 status；
     贴近档是 warn；不需要静区的侧（1D 上下）零值不报。
  2. **放大率边界四值** —— `0.2640`/`0.6600` 不报，`0.2639`/`0.6601` 报。
  3. **DPI 边界四值** —— `1.4999`/`1.5000`/`1.9999`/`2.0000` 逐条；外加 §8 的三个
     实算例（`120→1.559 warn` / `100→1.299 error` / `203→2.637 ok`）。
  4. **条高模块比** —— 由数据阈值驱动，未核时降级。
  5. **纪律** —— 判定模块不读文件；缺参只产 `input_complete`；工程判据不降级。

期望值一律**由输入重算**，不抄一段报告再比对（`plan/04` §二.2）。
"""

import ast
import json
import pathlib

import pytest

from bpreflight import input as input_mod
from bpreflight import pipeline
from bpreflight import thresholds
from bpreflight.print import audit, common

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PRINT_DIR = REPO_ROOT / "src" / "bpreflight" / "print"


@pytest.fixture(scope="module")
def book():
    return thresholds.load_book()


@pytest.fixture(scope="module")
def profiles():
    from bpreflight.symbols import profiles as profiles_mod

    return profiles_mod.load()


def _payload(**overrides):
    base = {
        "schema": "bpreflight/spec/1",
        "symbol": "ean13",
        "x_dimension_mm": "0.330",
        "target_dpi": 203,
        "quiet_zone_mm": "5",
        "bar_height_mm": "22.85",
        "bar_color": "#000000",
        "space_color": "#FFFFFF",
        "illumination": "white",
    }
    base.update(overrides)
    return base


def _assess(book, profiles, **overrides):
    return audit.assess(book, profiles, _payload(**overrides))


def _ids(result):
    return [finding.id for finding in result.findings]


def _find(result, finding_id):
    found = [finding for finding in result.findings if finding.id == finding_id]
    assert found, "{} not in {}".format(finding_id, _ids(result))
    return found[0]


def _patched_book(statuses=None):
    """Copy the bundled book and flip the given quiet-zone row statuses.

    `statuses` maps `(symbol, side) -> (status, verified_at)`. Everything else is
    cloned verbatim so the only variable in the test is the status.
    """
    base = thresholds.load_book()
    quiet = json.loads(json.dumps(base.quiet_zone))
    for (symbol, side), (status, verified_at) in (statuses or {}).items():
        quiet["symbols"][symbol][side]["status"] = status
        quiet["symbols"][symbol][side]["verified_at"] = verified_at
    return thresholds.ThresholdBook(
        quiet, json.loads(json.dumps(base.gen_spec)), base.sha256, base.color_cases
    )


# --------------------------------------------------------------------------- #
# 1. 静区三档
# --------------------------------------------------------------------------- #


def test_zero_quiet_zone_is_an_error_regardless_of_threshold_status(book, profiles):
    """M3 第一验收点：零静区是**结构**事实，任何阈值状态都不许软化它。

    BinaryEye #616 类场景（静区不再生成）。两个方向都测：unverified（默认数据）
    与 verified（把 status 改成 verified）——severity 必须都是 error。

    另断言 `threshold_status: "not-applicable"`：结构档**不比较任何阈值**。报
    `unverified` 会让读者以为"这条错是因为数字没核、核了可能就没事了"——与事实
    相反。这正是它绕开 `gen_spec_finding`（唯一做降级的构造函数）的原因。
    """
    result = _assess(book, profiles, quiet_zone_mm="0")
    absent = [f for f in result.findings if f.id == "quiet_zone_absent"]
    # 1D：left/right 需要静区 → 两条；top/bottom 不需要 → 不报。
    assert len(absent) == 2, _ids(result)
    for finding in absent:
        assert finding.severity == "error"
        assert finding.threshold_status == "not-applicable"
        assert finding.threshold is None
        assert finding.fix["min_delta"]

    strict = audit.assess(book, profiles, _payload(quiet_zone_mm="0"),
                          strict_thresholds=True)
    for finding in strict.findings:
        if finding.id == "quiet_zone_absent":
            assert finding.severity == "error"
            assert finding.threshold_status == "not-applicable"

    # 换成 verified 仍是 error（结构档不读 status），状态仍是 not-applicable。
    verified = _patched_book(
        statuses={
            ("ean13", "left"): ("verified", "2026-10-27"),
            ("ean13", "right"): ("verified", "2026-10-27"),
        }
    )
    result = audit.assess(verified, profiles, _payload(quiet_zone_mm="0"))
    absent = [f for f in result.findings if f.id == "quiet_zone_absent"]
    assert len(absent) == 2
    assert all(f.severity == "error" for f in absent)
    assert all(f.threshold_status == "not-applicable" for f in absent)


def test_zero_quiet_zone_on_a_side_the_symbol_does_not_require_is_not_reported(book, profiles):
    """1D 的 top/bottom 不要求静区：0 是合法值，不许报。"""
    result = _assess(book, profiles, quiet_zone_mm={"left": "3.63", "right": "2.31",
                                                   "top": "0", "bottom": "0"})
    assert "quiet_zone_absent" not in _ids(result)


def test_2d_symbols_require_all_four_sides(book, profiles):
    """2D 的四边都承载定位/定时图形 → 任一侧为 0 都报。"""
    result = _assess(book, profiles, symbol="datamatrix", quiet_zone_mm=0,
                     bar_height_mm=None)
    absent = [f for f in result.findings if f.id == "quiet_zone_absent"]
    assert len(absent) == 4, _ids(result)


def test_insufficient_quiet_zone_reproduces_python_barcode_41(book, profiles):
    """`quiet_zone_mm=0.6, X=0.330` → 1.818 modules < 占位 modules_min。

    断言的是**机制**：`fix.to` 必须等于 `modules_min x x_dimension`，且 severity
    随 status 变化（unverified→warn，verified→error）。
    """
    result = _assess(book, profiles, quiet_zone_mm="0.6", target_dpi=203)
    finding = _find(result, "quiet_zone_insufficient")
    left = book.quiet_zone_entry("ean13", "left")
    assert finding.observed.startswith("1.818")
    assert finding.threshold_status == "unverified"
    assert finding.severity == "warn"
    assert finding.fix["to"] == common.fixed(left["modules_min"] * 0.330)

    verified = _patched_book(
        statuses={("ean13", "left"): ("verified", "2026-10-27"),
                  ("ean13", "right"): ("verified", "2026-10-27")}
    )
    result = audit.assess(verified, profiles, _payload(quiet_zone_mm="0.6", target_dpi=203))
    assert all(
        f.severity == "error"
        for f in result.findings
        if f.id == "quiet_zone_insufficient"
    )


def test_marginal_band_is_a_warn(book, profiles):
    """`modules_min <= qz < modules_min x factor` → warn，并给出出带目标。"""
    left = book.quiet_zone_entry("ean13", "left")
    factor = book.engineering("quiet_zone_marginal_factor")["value"]
    in_band = left["modules_min"] * 1.05 * 0.330  # just above the floor, inside the band
    result = _assess(book, profiles, quiet_zone_mm=common.fixed(in_band), target_dpi=300)
    finding = _find(result, "quiet_zone_marginal")
    assert finding.severity == "warn"
    assert finding.threshold_status == "unverified"
    assert finding.fix["to"] == common.fixed(
        left["modules_min"] * float(factor) * 0.330
    )


# --------------------------------------------------------------------------- #
# 2. 放大率边界四值
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "x_dimension, expect_id",
    [
        ("0.2640", None),                # exactly 80% -> inside
        ("0.2639", "magnification_below_range"),
        ("0.6600", None),                # exactly 200% -> inside
        ("0.6601", "magnification_above_range"),
    ],
)
def test_magnification_boundaries(book, profiles, x_dimension, expect_id):
    """§8.3 的四值边界逐条：边界内侧不报，越界一格就报。"""
    result = _assess(
        book, profiles, x_dimension_mm=x_dimension, target_dpi=300,
        quiet_zone_mm="5", bar_height_mm=None,
    )
    magnitude = [f for f in result.findings if "magnification" in f.id]
    if expect_id is None:
        assert magnitude == [], [f.id for f in magnitude]
    else:
        assert [f.id for f in magnitude] == [expect_id]
        assert magnitude[0].severity == "warn"
        assert magnitude[0].fix["to"]


# --------------------------------------------------------------------------- #
# 3. DPI 边界 + §8 的三个实算例
# --------------------------------------------------------------------------- #


def test_dots_per_module_boundary_semantics_are_declared(book):
    """边界语义写在数据里（`error_below < warn_below`），不是代码里的隐式约定。

    `< error_below` 才 error、`< warn_below` 才 warn ⇒ 恰好等于阈值时落**上一档**。
    这正是 §8.3 要求的「`1.5000` 判 warn、`2.0000` 判 ok」的来源。
    """
    from decimal import Decimal

    rule = book.engineering("dots_per_module")
    assert Decimal(rule["error_below"]) < Decimal(rule["warn_below"])
    assert "status" not in rule and "verified_at" not in rule


@pytest.mark.parametrize(
    "dots, expect_id, expect_severity",
    [
        ("1.4999", "raster_alias_high_risk", "error"),
        ("1.5000", "raster_alias_risk", "warn"),
        ("1.9999", "raster_alias_risk", "warn"),
        ("2.0000", None, None),
    ],
)
def test_dots_per_module_boundaries(book, profiles, dots, expect_id, expect_severity):
    """四个边界值逐条：由目标点数反解 DPI（`dpi = dots x mm_per_inch / x`）。

    反解会带来 DPI 的取整误差，所以这里直接调 `raster.check` 的**判定入口**用的是
    Decimal 精确算术 —— 把 X 固定为 25.4 mm，DPI 就等于目标点数。
    """
    from decimal import Decimal

    x_dimension = Decimal(book.mm_per_inch)  # X == mm_per_inch -> dots == dpi
    result = audit.assess(
        book,
        profiles,
        _payload(
            x_dimension_mm=str(x_dimension),
            target_dpi=str(Decimal(dots)),
            quiet_zone_mm="500",   # far above every minimum: isolate the raster probe
            bar_height_mm=None,
        ),
    )
    raster = [f for f in result.findings if f.id.startswith("raster_alias")]
    if expect_id is None:
        assert raster == [], [f.id for f in raster]
    else:
        assert [f.id for f in raster] == [expect_id]
        assert raster[0].severity == expect_severity
        assert raster[0].threshold_status == "not-applicable"
        assert raster[0].fix["to"]


def test_documented_dpi_examples(book, profiles):
    """§8/`plan/01` 的三个实算例：120→1.559 warn / 100→1.299 error / 203→2.637 ok。"""
    cases = [
        (120, "1.559", "raster_alias_risk", "warn"),
        (100, "1.299", "raster_alias_high_risk", "error"),
        (203, "2.637", None, None),
    ]
    for dpi, observed, finding_id, severity in cases:
        result = _assess(book, profiles, target_dpi=dpi, quiet_zone_mm="5",
                         bar_height_mm=None)
        raster = [f for f in result.findings if f.id.startswith("raster_alias")]
        if finding_id is None:
            assert raster == [], (dpi, [f.id for f in raster])
        else:
            assert [f.id for f in raster] == [finding_id], dpi
            assert raster[0].observed.startswith(observed), raster[0].observed
            assert raster[0].severity == severity


# --------------------------------------------------------------------------- #
# 4. 条高
# --------------------------------------------------------------------------- #


def test_bar_height_uses_the_symbol_threshold_and_downgrades(book, profiles):
    """条高模块比低于该符号的阈值 → `bar_height_insufficient`（未核时 warn）。"""
    entry = book.gen_spec_entry("bar_height_modules_min_ean13")
    too_short = float(entry["value"]) * 0.330 * 0.5
    result = _assess(book, profiles, bar_height_mm=common.fixed(too_short))
    finding = _find(result, "bar_height_insufficient")
    assert finding.threshold_status == "unverified"
    assert finding.severity == "warn"
    assert finding.fix["to"] == common.fixed(float(entry["value"]) * 0.330)


def test_bar_height_is_not_applied_to_symbols_without_a_threshold(book, profiles):
    """没有该符号的条高阈值就**不判**，不借别人的数字。"""
    result = _assess(book, profiles, symbol="code128", bar_height_mm="1.0",
                     quiet_zone_mm="5", bar_color=None, space_color=None,
                     illumination=None)
    assert "bar_height_insufficient" not in _ids(result)


def test_bar_height_is_optional(book, profiles):
    """没给条高不是"缺参"：它是可选判据，其余五项照判。"""
    result = _assess(book, profiles, bar_height_mm=None)
    assert "input_incomplete" not in _ids(result)
    assert result.judged is True


# --------------------------------------------------------------------------- #
# 5. 缺参拒判 / 三态 / 纪律
# --------------------------------------------------------------------------- #


def test_missing_x_dimension_produces_only_input_incomplete(book, profiles):
    """§8.9 G3：缺 `x_dimension_mm` ⇒ 只有 `input_incomplete`，一条派生结论都没有。"""
    payload = _payload()
    del payload["x_dimension_mm"]
    result = audit.assess(book, profiles, payload)
    assert _ids(result)[0] == "input_incomplete"
    for prefix in ("quiet_zone_", "magnification_", "raster_", "bar_height_"):
        assert not [i for i in _ids(result) if i.startswith(prefix)], _ids(result)
    assert result.judged is False


@pytest.mark.parametrize("missing", ["target_dpi", "quiet_zone_mm"])
def test_missing_geometry_fields_are_refused(book, profiles, missing):
    payload = _payload()
    del payload[missing]
    result = audit.assess(book, profiles, payload)
    finding = _find(result, "input_incomplete")
    assert missing in finding.observed
    assert finding.severity == "error"
    assert finding.fix["to"]


def test_colour_is_judged_even_when_geometry_is_incomplete(book, profiles):
    """颜色只依赖两个颜色 + 照明：几何缺参不影响这一项（但它自己仍判 input_incomplete）。"""
    payload = {"schema": "bpreflight/spec/1", "bar_color": "#C8102E",
               "space_color": "#FFFFFF", "illumination": "red"}
    result = audit.assess(book, profiles, payload)
    ids = _ids(result)
    assert "wavelength_reflectance_collapse" in ids
    assert "input_incomplete" in ids
    assert "surface_effect_unmodeled" not in ids


def test_zero_x_dimension_is_x_dimension_missing(book, profiles):
    """§8.3：`x_dimension_mm <= 0` → `x_dimension_missing`，不产其它比值结论。"""
    result = _assess(book, profiles, x_dimension_mm="0")
    assert "x_dimension_missing" in _ids(result)
    for prefix in ("quiet_zone_", "magnification_", "raster_"):
        assert not [i for i in _ids(result) if i.startswith(prefix)], _ids(result)


def test_engineering_heuristics_never_downgrade(book, profiles):
    """DPI 与颜色两项**不参与**未核降级：strict 与默认必须给出同一 severity。"""
    soft = _assess(book, profiles, target_dpi=100, quiet_zone_mm="5", bar_height_mm=None)
    hard = audit.assess(
        book, profiles,
        _payload(target_dpi=100, quiet_zone_mm="5", bar_height_mm=None),
        strict_thresholds=True,
    )
    soft_raster = _find(soft, "raster_alias_high_risk")
    hard_raster = _find(hard, "raster_alias_high_risk")
    assert soft_raster.severity == hard_raster.severity == "error"
    assert soft_raster.threshold_status == hard_raster.threshold_status == "not-applicable"


def test_strict_thresholds_restores_error_for_gen_spec_items(book, profiles):
    """gen-spec 项反过来：strict 下同样的输入必须由 warn 变 error。"""
    soft = _assess(book, profiles, quiet_zone_mm="0.6")
    hard = audit.assess(book, profiles, _payload(quiet_zone_mm="0.6"),
                        strict_thresholds=True)
    assert _find(soft, "quiet_zone_insufficient").severity == "warn"
    assert _find(hard, "quiet_zone_insufficient").severity == "error"


def test_print_modules_do_not_read_files():
    """判定模块不 `open()`：阈值册由 pipeline 装载后传入（AST 判据，与 M2 同款）。"""
    offenders = []
    scanned = 0
    for path in sorted(PRINT_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        scanned += 1
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                offenders.append("{}:{}".format(path.name, node.lineno))
            elif isinstance(func, ast.Attribute) and func.attr == "open":
                offenders.append("{}:{}".format(path.name, node.lineno))
    assert scanned > 0, "print/ 下没有 .py —— 判据空跑"
    assert offenders == []


def test_print_modules_carry_no_threshold_literals_of_their_own(book, profiles):
    """阈值全部来自数据：把阈值册换成改过的快照，判定必须跟着变。"""
    louder = _patched_book()
    louder_rule = dict(louder.gen_spec["engineering_heuristics"]["dots_per_module"])
    louder_rule["warn_below"] = "3.0"
    gen = json.loads(json.dumps(louder.gen_spec))
    gen["engineering_heuristics"]["dots_per_module"] = louder_rule
    patched = thresholds.ThresholdBook(
        louder.quiet_zone, gen, louder.sha256, louder.color_cases
    )
    payload = _payload(target_dpi=203, quiet_zone_mm="5", bar_height_mm=None)
    relaxed = audit.assess(louder, profiles, payload)
    tightened = audit.assess(patched, profiles, payload)
    # 2.637 在 2.0 之上（ok），在 3.0 之下（warn）——判定确实跟着数据走。
    assert [f for f in relaxed.findings if f.id.startswith("raster_alias")] == []
    assert [f.id for f in tightened.findings if f.id.startswith("raster_alias")] == [
        "raster_alias_risk"
    ]


def test_pipeline_marks_m3_as_implemented():
    report = pipeline.run(_payload(), {"file": "spec.json"})
    assert "M3" in pipeline.IMPLEMENTED_MODULES
    assert "module_not_implemented:M3" not in report.skipped


def test_pipeline_print_only_spec_does_not_ask_for_data_layer_fields(book):
    """只给印刷参数的 spec：由 M3 判，不该再叠一条数据层的 `input_incomplete`。"""
    report = pipeline.run(_payload(), {"file": "spec.json"})
    ids = [f.id for f in report.findings]
    assert "input_incomplete" not in ids, ids


def test_pipeline_symbol_alone_is_not_a_print_input(book):
    """只给 symbol（与 M2 共用）不是"请求印刷层"，不许判 fail。"""
    payload = {"schema": "bpreflight/spec/1", "symbol": "ean13",
               "identifier": "4006381333931"}
    report = pipeline.run(payload, {"file": "spec.json"})
    assert "input_incomplete" not in [f.id for f in report.findings]
    assert not [s for s in report.skipped if s.startswith("input_incomplete:")]


def test_print_input_fields_exclude_symbol():
    assert "symbol" not in input_mod.PRINT_INPUT_FIELDS
    assert "x_dimension_mm" in input_mod.PRINT_INPUT_FIELDS
