"""M1 语义：字典整表解析 + `yymmd0` / `req` / `ex` 三个解释器。

做法：**用例从 `gs1_vectors.json` 读进来**，期望值不是抄的字符串，而是逐条
重算的（`plan/00` K2 的真值纪律）。用例里每一条都带 `source`，指得上官方
linter 单测或 `plan/05` 的 DoD 条目。

三个"必须一起成立"的对照（缺任何一条，另两条都能假绿）：

  · `(17)251200` 报 `dd00_last_day_of_month`(info) 且归一到当月最后一天；
  · `(17)251301` 仍必须 `invalid_date` —— 证明 DD=00 特例没有把日期校验关掉；
  · `req` 的 OR / AND 各一条正例 + 各一条反例。
"""

import pathlib

import pytest

from bpreflight.gs1 import dictionary, elements, validators, vectors

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: 整张表的规模。这组数是"解析了多少"的自证，不是装饰：字典换了版本而
#: 解析器悄悄少读几行时，这里会红。
EXPECTED_ENTRY_LINES = 224
EXPECTED_CONCRETE_AIS = 541


@pytest.fixture(scope="module")
def doc():
    return dictionary.load()


@pytest.fixture(scope="module")
def resolution():
    return vectors.load_century_resolution()


def _run(text, doc, resolution=None):
    parsed, issues = elements.parse(text, doc)
    return validators.validate_element_string(doc, issues, parsed, resolution)


def _ids(result):
    return sorted(finding.id for finding in result.findings)


def _targets(result, finding_id):
    return sorted(f.target for f in result.findings if f.id == finding_id)


# --------------------------------------------------------------------------- #
# 字典整表解析（"抽样 8 行就对"不算证据）
# --------------------------------------------------------------------------- #


def test_whole_dictionary_parses(doc):
    """整张表逐行解析；解析行数进测试结论（非空跑自证）。"""
    stats = doc.stats
    print(
        "字典解析：{lines_total} 行 / {lines_comment} 注释 / {entries} 条目 / "
        "{concrete_ais} 具体 AI / {components} 组件 / req {with_req} / ex {with_ex}".format(
            **stats
        )
    )
    assert stats["entries"] == EXPECTED_ENTRY_LINES, (
        "字典条目数变了（{} != {}）：是上游更新了，还是解析器漏读了？".format(
            stats["entries"], EXPECTED_ENTRY_LINES
        )
    )
    assert stats["concrete_ais"] == EXPECTED_CONCRETE_AIS
    assert len(doc) == EXPECTED_CONCRETE_AIS
    assert stats["with_req"] > 0 and stats["with_ex"] > 0, "req/ex 一条都没解析到 —— 空跑"
    assert stats["components"] > stats["entries"], "组件数少于条目数，解析退化了"


def test_dictionary_digest_matches_manifest(doc):
    """字典哈希与 `dict_manifest.json` 一致（`plan/00` 台账行）。"""
    manifest = dictionary.load_manifest()
    assert doc.sha256 == manifest["sha256"]
    assert doc.dict_version == manifest["dict_version"]
    assert doc.source_path == manifest["path"]


def test_known_entries_carry_the_documented_fields(doc):
    """抽 4 条已知条目做**字段级**断言（断言字段值，不取注释文字）。"""
    ai01 = doc.require("01")
    assert ai01.title == "GTIN"
    assert ai01.fixed_length == 14
    assert ai01.components[0].linters == ("csum", "gcppos2")
    assert ai01.ex_patterns == ("255", "37")
    assert ai01.req_groups == ()
    assert ai01.starred is True

    ai10 = doc.require("10")
    assert ai10.fixed_length is None
    assert ai10.req_groups == (("01",), ("02",), ("03",), ("8006",), ("8026",))

    ai250 = doc.require("250")
    assert ai250.req_groups == (("01", "21"), ("03", "21"), ("8006", "21"))
    assert ai250.min_length == 1 and ai250.max_length == 30

    ai8003 = doc.require("8003")
    assert [component.optional for component in ai8003.components] == [False, False, True]
    assert ai8003.components[0].linters == ("zero",)
    assert ai8003.components[1].linters == ("csum", "gcppos1")


def test_ranges_are_expanded_and_patterns_are_not_materialised_in_the_table(doc):
    """`3100-3105` 这类区间必须展开成具体 AI；`310n` 只出现在属性里。"""
    for ai in ("3100", "3105"):
        assert ai in doc
    assert "310" not in doc, "区间被当成单条 AI 用了"
    assert doc.require("3100").entry_ai == "3100-3105"
    assert doc.require("3105").title == "NET WEIGHT (kg)"


def test_req_groups_only_reference_AIs_that_exist_or_patterns(doc):
    """每个 req 成员要么是已定义的 AI，要么是 `n` 通配模式。"""
    concrete = set(doc.entries)
    for ai in sorted(doc.entries):
        for group in doc.require(ai).req_groups:
            for member in group:
                if "n" in member:
                    assert member.count("n") <= 2, member
                else:
                    assert member in concrete, "req={} 指向了不存在的 AI".format(member)


# --------------------------------------------------------------------------- #
# yymmd0：DD=00 是特例，不是"关掉日期校验"
# --------------------------------------------------------------------------- #


def _vector_cases(section):
    return vectors.load()[section]["cases"]


@pytest.mark.parametrize("case", _vector_cases("yymmd0"), ids=lambda c: c["value"])
def test_yymmd0_vectors(case, doc, resolution):
    """date 向量逐条过：`expect` 是数据，判定由实现重算。"""
    result = _run("({}){}".format(case["ai"], case["value"]), doc, resolution)
    ids = _ids(result)
    expect = case["expect"]
    if expect == "ok":
        assert "invalid_date" not in ids, case
        assert "dd00_last_day_of_month" not in ids, case
    elif expect == "dd00":
        assert "invalid_date" not in ids, case
        assert "dd00_last_day_of_month" in ids, case
        observed = [
            f.observed for f in result.findings if f.id == "dd00_last_day_of_month"
        ][0]
        assert observed.endswith(case["normalized"]), "{} -> {}".format(case, observed)
    else:
        assert "invalid_date" in ids, case
        assert "dd00_last_day_of_month" not in ids, case


def test_dd00_normalizes_to_last_day_of_month(doc, resolution):
    """`(17)251200` → 2025-12-31，且**不得**报 `invalid_date`（M1 第一验收点）。"""
    result = _run("(17)251200", doc, resolution)
    assert "invalid_date" not in _ids(result)
    assert _ids(result).count("dd00_last_day_of_month") == 1
    finding = [f for f in result.findings if f.id == "dd00_last_day_of_month"][0]
    assert finding.severity == "info", "DD=00 是提示不是错误"
    assert finding.observed.endswith("2025-12-31")


def test_control_case_still_reports_invalid_date(doc, resolution):
    """`(17)251301` 必须 `invalid_date` —— 与上一条构成一对，缺一不可。"""
    result = _run("(17)251301", doc, resolution)
    assert "invalid_date" in _ids(result)
    finding = [f for f in result.findings if f.id == "invalid_date"][0]
    assert finding.severity == "error"
    assert finding.fix["to"]


def test_month_bounds_use_calendar_not_a_table():
    """月份越界由 `calendar` 判定（闰年/月长都交给标准库）。"""
    resolution = vectors.load_century_resolution()
    bad_months = ["250001", "251301", "259900"]
    for value in bad_months:
        status, normalized, _ = validators.resolve_date(value, "yymmd0", resolution)
        assert status == "invalid_date", value
        assert normalized is None


def test_two_digit_year_expansion_matches_upstream_window():
    """YY 展开按上游 `CURRENT_YEAR` 窗口（固定值，不读系统时钟）。"""
    resolution = vectors.load_century_resolution()
    reference = resolution["reference_year_yy"]
    window = resolution["century_window"]
    centuries = resolution["centuries"]

    def expected(yy):
        offset = yy - reference
        if offset >= window + 1:
            century = centuries["high"]
        elif offset > -(window):
            century = centuries["mid"]
        else:
            century = centuries["low"]
        return century * 100 + yy

    for yy in range(100):
        assert validators._expand_two_digit_year(yy, resolution) == expected(yy)


def test_resolution_is_pinned_not_clock_derived():
    """口径来自数据；固定值意味着同一输入在任何年份跑出同一结果（K10）。"""
    resolution = vectors.load_century_resolution()
    assert isinstance(resolution["reference_year_yy"], int)
    assert "source" in resolution and "lint_yymmd0" in resolution["source"]


# --------------------------------------------------------------------------- #
# req：OR / AND
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("case", _vector_cases("req"), ids=lambda c: c["name"])
def test_req_vectors(case, doc, resolution):
    """每条 req 用例：期望的 (`id`, `ai`) 组合必须**正好**出现，且不许多报。"""
    result = _run(case["element_string"], doc, resolution)
    expected = sorted(
        (item["id"], item["ai"]) for item in case["expect_findings"]
    )
    actual = sorted(
        (f.id, f.target.split(":")[1])
        for f in result.findings
        if f.id == "missing_required_ai"
    )
    assert actual == expected, case["name"]


def test_req_or_and_are_read_from_the_dictionary(doc):
    """`req=01,02,03` 是 OR；`req=01+21` 是 AND —— 语义来自字典文本，不是代码特例。"""
    or_entry = doc.require("10")
    and_entry = doc.require("250")
    assert or_entry.req_groups == (("01",), ("02",), ("03",), ("8006",), ("8026",))
    assert all(len(group) == 1 for group in or_entry.req_groups)
    assert and_entry.req_groups == (("01", "21"), ("03", "21"), ("8006", "21"))
    assert all(len(group) == 2 for group in and_entry.req_groups)


# --------------------------------------------------------------------------- #
# ex：互斥
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("case", _vector_cases("ex"), ids=lambda c: c["name"])
def test_ex_vectors(case, doc, resolution):
    result = _run(case["element_string"], doc, resolution)
    expected = sorted(
        (item["id"], item["ai"]) for item in case["expect_findings"]
    )
    actual = sorted(
        (f.id, f.target.split(":")[1])
        for f in result.findings
        if f.id == "mutually_exclusive_ai"
    )
    assert actual == expected, case["name"]


def test_exclusion_is_symmetric_when_both_sides_declare_it(doc, resolution):
    """`01` 声明 ex=255 且 `255` 声明 ex=01 → 两侧各报一条（不是"只报一侧就算过"）。"""
    result = _run("(01)09501101530003(255)0950110153007", doc, resolution)
    targets = _targets(result, "mutually_exclusive_ai")
    assert targets == ["ai:01:ex:255", "ai:255:ex:01"]


def test_mutually_exclusive_finding_has_an_actionable_fix(doc, resolution):
    result = _run("(01)09501101530003(255)0950110153007", doc, resolution)
    finding = [f for f in result.findings if f.id == "mutually_exclusive_ai"][0]
    assert finding.severity == "error"
    assert finding.fix["to"] in ("01", "255")
    assert finding.evidence["kind"] == "dict-line"
    assert "gs1-syntax-dictionary.txt" in finding.evidence["ref"]


# --------------------------------------------------------------------------- #
# 结构面：长度 / 字符集 / unknown / 校验位
# --------------------------------------------------------------------------- #


def test_invalid_length_names_the_dictionary_bound(doc, resolution):
    result = _run("(01)0950", doc, resolution)
    assert _ids(result) == ["invalid_length"]
    finding = result.findings[0]
    assert finding.fix["to"] == "14"
    assert finding.fix["unit"] == "characters"


def test_invalid_charset_is_detected_for_numeric_fields(doc, resolution):
    result = _run("(01)09501101530O03", doc, resolution)
    assert "invalid_charset" in _ids(result)


def test_unknown_ai_is_an_error_with_a_fix(doc, resolution):
    result = _run("(65)X", doc, resolution)
    assert "unknown_ai" in _ids(result)
    finding = [f for f in result.findings if f.id == "unknown_ai"][0]
    assert finding.severity == "error"
    assert finding.fix["to"]


def test_bad_check_digit_is_reported_with_the_corrected_value(doc, resolution):
    result = _run("(01)09501101530004", doc, resolution)
    findings = [f for f in result.findings if f.id == "invalid_csum"]
    assert findings, "错误校验位必须报"
    assert findings[0].fix["to"] == "09501101530003", "fix 要给可用的目标值，不是空话"


def test_valid_element_string_produces_no_error(doc, resolution):
    """干净输入必须真的干净——否则前面的"报得出来"可能只是恒报。"""
    result = _run("(01)09501101530003(17)251231(10)ABC123", doc, resolution)
    assert _ids(result) == [], [(f.id, f.observed) for f in result.findings]


# --------------------------------------------------------------------------- #
# FNC1 原生串形态
# --------------------------------------------------------------------------- #


def test_raw_fnc1_form_parses_to_the_same_elements(doc, resolution):
    """`(01)…(10)…` 与 FNC1 原生串两种形态必须等价（后者按 AI 定长切分）。"""
    bracketed = "(01)09501101530003(10)BATCH1"
    raw = "01" + "09501101530003" + "\x1d" + "10BATCH1"
    parsed_bracketed, issues_bracketed = elements.parse(bracketed, doc)
    parsed_raw, issues_raw = elements.parse(raw, doc)
    assert issues_bracketed == [] and issues_raw == []
    assert [(e.ai, e.value) for e in parsed_bracketed] == [
        (e.ai, e.value) for e in parsed_raw
    ] == [("01", "09501101530003"), ("10", "BATCH1")]

    assert _ids(_run(bracketed, doc, resolution)) == _ids(_run(raw, doc, resolution))


def test_raw_form_finds_the_longest_matching_ai(doc):
    """AI 前缀扫描取最长匹配：`8006` 不会被读成 `80`（表里也没有 `80`）。"""
    # 8006 = N14,csum,gcppos2 + N4,pieceoftotal → 定长 18，加上 4 位 AI 共 22 字符。
    parsed, issues = elements.parse("8006" + "09501101530003" + "0002", doc)
    assert issues == []
    assert parsed[0].ai == "8006"
    assert parsed[0].value == "095011015300030002"


# --------------------------------------------------------------------------- #
# 不可判通道
# --------------------------------------------------------------------------- #


def test_unimplemented_linters_are_declared_not_silent(doc, resolution):
    """字典点名、本棒未实现的 linter 走 `skipped`，不冒充已判（§8.9 G2 同款）。"""
    result = _run("(01)09501101530003", doc, resolution)
    assert validators.SKIP_GCP_LOOKUP in result.skipped, (
        "gcppos2 需要 GCP 分配库（GEPIR，联网）才能判；必须标不可判"
    )


def test_interpreted_linters_match_the_documented_four(doc):
    """实际解释的 linter 就是 D1 允许的那几个，不多不少。"""
    assert set(validators.INTERPRETED_LINTERS) == {
        "csum",
        "yymmd0",
        "yymmdd",
        "yyyymmd0",
        "yyyymmdd",
    }
    assert set(validators.GCP_LOOKUP_LINTERS) == {"gcppos1", "gcppos2"}
    # 字典里出现的 linter 必须每个都有归宿（解释 / 明确不可判），否则就是"静默略过"。
    seen = set()
    for ai in doc.entries:
        seen.update(doc.require(ai).linters)
    covered = set(validators.INTERPRETED_LINTERS) | set(validators.GCP_LOOKUP_LINTERS)
    assert seen - covered, "字典里已无未覆盖 linter —— 这条判据该改写了"


def test_every_uncovered_linter_is_named_in_the_skip_list(doc):
    """未被解释的 linter 必须在报告里**点名**出现（不许静默略过）。"""
    result = _run("(01)09501101530003(422)840", doc)
    named = [item for item in result.skipped if item.startswith("linter_not_implemented:")]
    assert named, "iso3166 这类未实现 linter 必须进 skipped 名单"


# --------------------------------------------------------------------------- #
# 裸标识（GTIN-8/12/13/14、SSCC-18）
# --------------------------------------------------------------------------- #


def test_identifier_check_digit_is_validated():
    """裸标识：校验位 + 长度 + 字符集。长度表来自向量文件，不写在代码里。"""
    lengths = vectors.identifier_lengths()
    assert validators.validate_identifier("09501101530003", lengths).findings == []
    assert validators.validate_identifier("09501101530004", lengths).findings[0].id == (
        "invalid_csum"
    )
    # 15 位不在 GTIN/SSCC 家族里（8/12/13/14/18）——注意 13 位本身是合法的 GTIN-13。
    assert validators.validate_identifier("095011015300034", lengths).findings[0].id == (
        "invalid_length"
    )
    assert validators.validate_identifier("0950110153000X", lengths).findings[0].id == (
        "invalid_charset"
    )


def test_identifier_family_labels_come_from_the_vector_file():
    lengths = vectors.identifier_lengths()
    assert lengths["14"] == "GTIN-14"
    assert lengths["18"] == "SSCC-18"
    assert sorted(lengths, key=int) == ["8", "12", "13", "14", "18"]