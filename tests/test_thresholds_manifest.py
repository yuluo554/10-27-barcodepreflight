"""阈值数据的形状契约：每个阈值项可溯源、三态字段齐、工程判据不带 status。

这道题的全部可信度都压在"阈值不是数字而是数据"上（`data/README.md` §5、§8.2）。
判定对不对取决于数据对不对，所以数据的形状本身要是可断言的：

  · `gen-spec` 项：`source` / `status` / `verified_at` / `basis` 四件齐，
    `status` 只能是 `verified`/`unverified`，且 `verified` 必须有日期、`unverified`
    必须为 null（否则"未核"会伪装成"已核"）；
  · 每一项都要能追到 `data/README.md` §5 的一行（这里用 `source` 非空 + 三条
    已知来源词族来钉，而不是靠人读）；
  · `engineering-heuristic` 项：**不许**有 status（K8）；
  · 静区：`required` 是结构事实，必须是 bool 且与"是否 1D"一致。
"""

from decimal import Decimal, InvalidOperation

import pytest

from bpreflight import input as input_mod
from bpreflight import thresholds

GEN_SPEC_FIELDS = ("source", "status", "verified_at", "basis")


@pytest.fixture(scope="module")
def book():
    return thresholds.load_book()


def _items(book):
    """Every gen-spec threshold item with its dotted path."""
    for symbol in sorted(book.quiet_zone["symbols"]):
        for side in sorted(book.quiet_zone["symbols"][symbol]):
            yield "quiet_zone.{}.{}".format(symbol, side), book.quiet_zone["symbols"][symbol][side]
    for key in sorted(book.gen_spec["values"]):
        yield "gen_spec.{}".format(key), book.gen_spec["values"][key]


# --------------------------------------------------------------------------- #
# 1. 三态字段
# --------------------------------------------------------------------------- #


def test_every_gen_spec_item_carries_the_three_state_fields(book):
    count = 0
    for where, entry in _items(book):
        for field in GEN_SPEC_FIELDS:
            assert field in entry, "{} misses {}".format(where, field)
        assert entry["basis"] == "gen-spec", where
        assert entry["status"] in ("verified", "unverified"), where
        assert isinstance(entry["source"], str) and entry["source"], where
        count += 1
    assert count > len(book.quiet_zone["symbols"]), "阈值项少于符号数 —— 空跑"


def test_verified_items_have_a_date_and_unverified_have_none(book):
    """两条一起才成立：否则"改 status 不补日期"能把未核洗成已核。"""
    for where, entry in _items(book):
        if entry["status"] == "verified":
            assert entry["verified_at"], "{} is verified but has no date".format(where)
        else:
            assert entry["verified_at"] is None, "{} is unverified but carries a date".format(
                where
            )


def test_numeric_threshold_values_parse_as_decimals(book):
    """阈值一律定点字符串：能转 Decimal 才允许进判定（K7）。"""
    for where, entry in _items(book):
        # quiet_zone 的 modules_min 是 int（模块数），gen_spec 的 value 是字符串。
        raw = entry.get("value", entry.get("modules_min"))
        assert raw is not None, where
        try:
            Decimal(str(raw))
        except (InvalidOperation, ValueError):
            raise AssertionError("{} value is not numeric: {!r}".format(where, raw))


def test_no_verified_item_exists_yet(book):
    """本轮没有 GenSpec 原表：全部未核。这条在核对之后应被**删掉并留痕**。

    留着它的意义：任何"顺手改一项 status"的改动都会立刻红，逼人回答
    "你拿到原表了吗、来源写在哪"（`plan/04` §三）。
    """
    for where, entry in _items(book):
        assert entry["status"] == "unverified", (
            "{} 被标成 verified —— 核对依据必须同提交写进 data/README.md §5".format(where)
        )


def test_unverified_keys_are_enumerable_and_sorted(book):
    keys = book.unverified_keys()
    assert keys
    assert keys == sorted(keys)
    assert "quiet_zone.ean13.left" in keys
    assert "gen_spec.nominal_x_mm" in keys


# --------------------------------------------------------------------------- #
# 2. 工程判据：没有 status（K8）
# --------------------------------------------------------------------------- #


def test_engineering_heuristics_carry_no_status(book):
    for key, entry in book.gen_spec["engineering_heuristics"].items():
        if key == "note":
            continue
        assert "status" not in entry, key
        assert "verified_at" not in entry, key
        assert entry["basis"] == "engineering-heuristic", key


def test_engineering_entries_used_by_m3_all_exist(book):
    """M3 读的每个工程判据键都必须在数据里（缺键 = 断链，不是默认值）。"""
    for key in (
        "dots_per_module",
        "contrast_ratio",
        "wavelength_reflectance_delta_min",
        "quiet_zone_marginal_factor",
    ):
        entry = book.engineering(key)
        assert entry["basis"] == "engineering-heuristic"


def test_engineering_status_is_not_applicable(book):
    """工程判据的 `threshold_status` 恒 `not-applicable`，永不随 strict 变。"""
    for key in ("dots_per_module", "contrast_ratio", "wavelength_reflectance_delta_min"):
        assert book.status_of(book.engineering(key)) == "not-applicable"


def test_loader_rejects_a_status_on_an_engineering_entry(book):
    """变异：给工程判据加 status → 装载期必须拒（否则降级会漏进来）。"""
    import copy

    doc = copy.deepcopy(book.gen_spec)
    doc["engineering_heuristics"]["dots_per_module"]["status"] = "unverified"
    with pytest.raises(thresholds.ThresholdError):
        thresholds._validate_gen_spec(doc)


def test_loader_rejects_a_gen_spec_item_without_source(book):
    import copy

    doc = copy.deepcopy(book.gen_spec)
    del doc["values"]["nominal_x_mm"]["source"]
    with pytest.raises(thresholds.ThresholdError):
        thresholds._validate_gen_spec(doc)


# --------------------------------------------------------------------------- #
# 3. 静区：required 是结构事实
# --------------------------------------------------------------------------- #


def test_every_quiet_zone_row_declares_required_as_a_bool(book):
    for where, entry in _items(book):
        if not where.startswith("quiet_zone."):
            continue
        assert isinstance(entry.get("required"), bool), where


def test_required_sides_match_the_symbol_geometry(book):
    """1D 只要求左右；2D 四边都要。这是结构事实，不能由 modules_min 推出。"""
    for symbol in sorted(book.quiet_zone["symbols"]):
        sides = book.quiet_zone["symbols"][symbol]
        required = sorted(side for side, row in sides.items() if row["required"])
        if symbol in ("qr", "datamatrix"):
            assert required == sorted(sides), symbol
        else:
            assert required == ["left", "right"], symbol


def test_every_profiled_symbol_has_a_quiet_zone_row(book):
    """符号表与静区表必须同集合：缺一行的符号会让 M3 在运行时抛 ThresholdError。"""
    from bpreflight.symbols import profiles

    assert set(book.quiet_zone["symbols"]) == set(profiles.load().names())
    assert set(book.quiet_zone["symbols"]) == set(input_mod.SUPPORTED_SYMBOLS)


def test_loader_rejects_a_missing_required_flag(book):
    import copy

    doc = copy.deepcopy(book.quiet_zone)
    del doc["symbols"]["ean13"]["left"]["required"]
    with pytest.raises(thresholds.ThresholdError):
        thresholds._validate_quiet_zone(doc)


# --------------------------------------------------------------------------- #
# 4. 颜色表：工程判据 + 用例覆盖
# --------------------------------------------------------------------------- #


def test_colour_cases_have_no_status_fields(book):
    for name, entry in book.color_cases["illuminations"].items():
        assert "status" not in entry, name
        assert "verified_at" not in entry, name


def test_colour_cases_declare_modelled_and_a_channel(book):
    for name, entry in book.color_cases["illuminations"].items():
        assert isinstance(entry.get("modelled"), bool), name
        if entry["modelled"]:
            assert entry.get("channel"), name
        else:
            assert entry.get("channel") is None, name


def test_loader_rejects_a_colour_case_without_expected(book):
    import copy

    doc = copy.deepcopy(book.color_cases)
    del doc["cases"][0]["expected"]
    with pytest.raises(thresholds.ThresholdError):
        thresholds._validate_color_cases(doc)


def test_every_supported_illumination_is_in_the_table(book):
    """`input.ILLUMINATIONS` 与数据表同集合：少一个就是"支持却判不了"。"""
    assert set(book.color_cases["illuminations"]) == set(input_mod.ILLUMINATIONS)
