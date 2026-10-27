"""M2 符号层：数据驱动、跨符号等价性、`tie_break`、不复制校验位。

判据分四组：

  1. **数据面**——八符号齐、每条规则带 `source`/`status`/`verified_at`、
     装载器对坏数据 fail-closed；
  2. **DoD**——三组跨符号等价性逐条给**具体原因**（字符集/长度/结构/模式），
     不写"国家前缀"这类要 GEPIR 联网才能判的措辞；
  3. **确定性**——`encoding_plan.segments` 切分唯一、`tie_break: longest-first` 落字段；
  4. **纪律**——判定模块不读文件、不定义第二份校验位；未核规则降级为 warn。

用例的期望值从"输入 + 规则"重算，不抄一段 plan 再比对。
"""

import ast
import json
import pathlib

import pytest

from bpreflight import input as input_mod
from bpreflight import pipeline
from bpreflight.gs1 import checksum, dictionary, elements
from bpreflight.symbols import feasibility, profiles

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def book():
    return profiles.load()


@pytest.fixture(scope="module")
def doc():
    return dictionary.load()


def _assess(book, doc, symbol, identifier=None, element_string=None, strict=False):
    parsed = None
    if element_string is not None:
        parsed, issues = elements.parse(element_string, doc)
        assert issues == [], (element_string, issues)
    return feasibility.assess(
        book,
        symbol,
        identifier=identifier,
        elements=parsed,
        strict_thresholds=strict,
    )


def _find(result, finding_id):
    found = [finding for finding in result.findings if finding.id == finding_id]
    assert found, "{} not in {}".format(finding_id, [f.id for f in result.findings])
    return found[0]


# --------------------------------------------------------------------------- #
# 1. 数据面：八符号 + 每条规则三态齐全 + 装载器 fail-closed
# --------------------------------------------------------------------------- #


def test_all_eight_symbols_are_profiled(book):
    assert set(book.names()) == set(input_mod.SUPPORTED_SYMBOLS)
    assert len(book.names()) == len(input_mod.SUPPORTED_SYMBOLS)


def _rule_entries(doc):
    for name in sorted(doc["symbols"]):
        raw = doc["symbols"][name]
        yield "symbols.{}.gs1".format(name), raw["gs1"]
        for charset in sorted(raw["charsets"]):
            yield "symbols.{}.charsets.{}".format(name, charset), raw["charsets"][charset]
        yield "symbols.{}.length".format(name), raw["length"]
        for index, mode in enumerate(raw["modes"]):
            yield "symbols.{}.modes[{}]".format(name, index), mode
        yield "symbols.{}.modules".format(name), raw["modules"]
        yield "symbols.{}.checksum".format(name), raw["checksum"]
        if raw.get("gtin_map"):
            yield "symbols.{}.gtin_map".format(name), raw["gtin_map"]


def test_every_rule_carries_source_status_verified_at(book):
    """每条规则都要能追到来源；本轮没有规范原文 ⇒ 全部 unverified + verified_at null。"""
    scanned = 0
    for where, rule in _rule_entries(book.doc):
        for field in ("source", "status", "verified_at"):
            assert field in rule, "{} misses {}".format(where, field)
        assert rule["status"] == profiles.STATUS_UNVERIFIED, where
        assert rule["verified_at"] is None, where
        assert rule["source"] in book.sources, where
        scanned += 1
    assert scanned > len(book.names()), "规则项少于符号数——空跑"


def test_tie_break_is_declared_in_data(book):
    assert book.tie_break == profiles.TIE_BREAK_LONGEST_FIRST


def test_loader_refuses_an_unknown_tie_break(book):
    doc = json.loads(json.dumps(book.doc))
    doc["tie_break"] = "shortest-first"
    with pytest.raises(profiles.ProfileError):
        profiles._validate(doc)


def test_loader_refuses_a_rule_without_source(book):
    doc = json.loads(json.dumps(book.doc))
    del doc["symbols"]["ean13"]["length"]["source"]
    with pytest.raises(profiles.ProfileError):
        profiles._validate(doc)


def test_loader_refuses_verified_without_date(book):
    doc = json.loads(json.dumps(book.doc))
    rule = doc["symbols"]["ean13"]["length"]
    rule["status"] = profiles.STATUS_VERIFIED
    rule["verified_at"] = None
    with pytest.raises(profiles.ProfileError):
        profiles._validate(doc)


# --------------------------------------------------------------------------- #
# 2. 跨符号等价性（M2 DoD 逐条）
# --------------------------------------------------------------------------- #


def test_padded_gtin_family_only_fits_its_own_length(book, doc):
    """12/13/14 位同族补位：各自只在对应长度的符号下合格。"""
    for data, symbol in (
        ("012345678905", "upca"),
        ("0012345678905", "ean13"),
    ):
        result = _assess(book, doc, symbol, identifier=data)
        assert result.plan is not None, (symbol, [f.id for f in result.findings])
        assert result.findings == [], (symbol, [f.id for f in result.findings])
        assert result.plan["symbol"] == symbol
        assert result.plan["checksum"]["value"] == data[-1]

    # 14 位：三只零售定长符号都不可，原因逐条点名长度；GS1 载体可以承载。
    gtin14 = "00012345678905"
    for symbol in ("ean8", "upca", "ean13"):
        result = _assess(book, doc, symbol, identifier=gtin14)
        assert result.plan is None, symbol
        finding = _find(result, "symbol_length_mismatch")
        assert "14 characters" in finding.observed, finding.observed
    carrier = _assess(book, doc, "gs1-128", identifier=gtin14)
    assert carrier.plan is not None


def test_padded_family_keeps_the_same_check_digit():
    """补位不改校验位——三例都由同一实现算出 5（`data/README.md` §8.1）。"""
    for data in ("012345678905", "0012345678905", "00012345678905"):
        assert data[-1] == checksum.gs1_check_digit(data[:-1])
        assert checksum.gs1_is_valid(data)


def test_ean13_vs_upca_reason_is_length_not_national_prefix(book, doc):
    """`4006381333931`：ean13 PASS、upca 不可，原因只许写长度/结构。"""
    data = "4006381333931"
    ean = _assess(book, doc, "ean13", identifier=data)
    assert ean.plan is not None
    assert ean.findings == []

    upca = _assess(book, doc, "upca", identifier=data)
    assert upca.plan is None
    finding = _find(upca, "symbol_length_mismatch")
    assert "13" in finding.observed and "12" in finding.observed
    rationale = (finding.fix or {}).get("rationale", "")
    text = " ".join(
        [finding.observed, rationale, finding.evidence.get("quote", "")]
    ).lower()
    assert "length" in text
    assert "prefix" not in text
    assert "前缀" not in " ".join([finding.observed, rationale])


def test_gs1_element_string_passes_in_gs1_128_and_needs_fnc1_in_code128(book, doc):
    element_string = "(01)09501101530003(10)BATCH1"

    gs1 = _assess(book, doc, "gs1-128", element_string=element_string)
    assert gs1.plan is not None
    assert [f for f in gs1.findings if f.severity in ("warn", "error")] == []

    plain = _assess(book, doc, "code128", element_string=element_string)
    finding = _find(plain, "gs1_data_missing_fnc1")
    assert finding.severity == "warn"  # 规则未核 → 降级
    assert finding.fix["to"] == "gs1-128"


def test_ai01_element_maps_to_the_retail_gtin_family(book, doc):
    """`(01)` 是 GTIN-14；去掉前导零就是零售形态（只有前导位真是 0 才行）。"""
    ean = _assess(book, doc, "ean13", element_string="(01)04006381333931")
    assert ean.plan is not None
    assert ean.plan["segments"][0]["text"] == "4006381333931"

    upca = _assess(book, doc, "upca", element_string="(01)04006381333931")
    assert upca.plan is None
    finding = _find(upca, "symbol_structure_mismatch")
    assert "zero" in finding.observed


# --------------------------------------------------------------------------- #
# 3. 切分唯一 / tie_break / 模块数
# --------------------------------------------------------------------------- #


def test_encoding_plan_is_unique_and_records_tie_break(book, doc):
    first = _assess(book, doc, "code128", identifier="123456")
    second = _assess(book, doc, "code128", identifier="123456")
    assert first.plan == second.plan
    assert first.plan["tie_break"] == profiles.TIE_BREAK_LONGEST_FIRST
    assert "".join(segment["text"] for segment in first.plan["segments"]) == "123456"
    # 纯数字串：C 与 B 同长时按 profile 的 priority 取 C（子集 C 两数字一个码字）。
    assert [segment["mode"] for segment in first.plan["segments"]] == ["C"]
    assert first.plan["segments"][0]["codewords"] == 3


def test_mode_switch_is_an_info_not_an_error(book, doc):
    """`\x1d` 只在子集 A、`abc` 只在子集 B —— 切分必须 A -> B 并报 info。"""
    result = _assess(book, doc, "code128", element_string="(10)BATCH1(10)abc")
    assert [segment["mode"] for segment in result.plan["segments"]] == ["A", "B"]
    finding = _find(result, "mode_switch_required")
    assert finding.severity == "info"


def test_total_modules_follows_the_profile_numbers(book, doc):
    """模块数由数据文件里的分段参数算出，不是代码里的容量表。"""
    plan = _assess(book, doc, "upca", identifier="012345678905").plan
    assert plan["total_modules"] == book.require("upca").modules["total"]

    code128 = _assess(book, doc, "code128", identifier="123456").plan
    modules = book.require("code128").modules
    # 3 个 C 码字 + start/check/stop（数据文件给出每一段）。
    expected = (
        modules["start_modules"]
        + 3 * modules["modules_per_codeword"]
        + modules["check_modules"]
        + modules["stop_modules"]
    )
    assert code128["total_modules"] == expected


# --------------------------------------------------------------------------- #
# 4. 字符集 / 容量 / 未核降级 / 结构纪律
# --------------------------------------------------------------------------- #


def test_charset_violation_names_the_characters(book, doc):
    result = _assess(book, doc, "code39", identifier="abc")
    assert result.plan is None
    finding = _find(result, "symbol_charset_violation")
    assert "'a'" in finding.observed
    assert finding.fix["to"]


def test_capacity_exceeded_gives_the_bound(book, doc):
    result = _assess(book, doc, "code39", identifier="X" * 81)
    finding = _find(result, "capacity_exceeded")
    assert "80" in finding.observed
    assert finding.fix["to"] == "80"


def test_unverified_rules_are_downgraded_and_strict_restores(book, doc):
    """与 §8.2 同一口径：未核规则的 error 默认降为 warn，--strict-thresholds 恢复。"""
    soft = _assess(book, doc, "ean13", identifier="012345678905")
    hard = _assess(book, doc, "ean13", identifier="012345678905", strict=True)
    soft_finding = _find(soft, "symbol_length_mismatch")
    hard_finding = _find(hard, "symbol_length_mismatch")
    assert soft_finding.severity == "warn"
    assert hard_finding.severity == "error"
    assert soft_finding.threshold_status == "unverified"
    assert hard_finding.threshold_status == "unverified"


def test_judgement_module_does_not_read_files():
    """判定模块不 `open()`：profile 由 pipeline 装载后传入（与 M1 同一性质）。"""
    path = REPO_ROOT / "src" / "bpreflight" / "symbols" / "feasibility.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "open":
            calls.append(node.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            calls.append(node.lineno)
    assert calls == []


def test_symbols_package_defines_no_check_digit(book, doc):
    """M2 不复制第二份校验位：符号层没有 check-digit 函数，且 import 了单一实现。"""
    defs = []
    for path in sorted((REPO_ROOT / "src" / "bpreflight" / "symbols").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and "check_digit" in node.name:
                defs.append("{}:{}".format(path.name, node.name))
    assert defs == []

    path = REPO_ROOT / "src" / "bpreflight" / "symbols" / "feasibility.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "bpreflight.gs1":
            imported.update(alias.name for alias in node.names)
    assert "checksum" in imported

    plan = _assess(book, doc, "ean13", identifier="4006381333931").plan
    assert plan["checksum"]["value"] == checksum.gs1_check_digit("400638133393")


# --------------------------------------------------------------------------- #
# 5. 接进 pipeline / 报告
# --------------------------------------------------------------------------- #


def _payload(**overrides):
    base = {
        "schema": "bpreflight/spec/1",
        "symbol": "ean13",
        "identifier": "4006381333931",
    }
    base.update(overrides)
    return base


def test_pipeline_reports_the_plan_and_drops_the_m2_skip():
    report = pipeline.run(_payload(), {"file": "spec.json"})
    assert report.encoding_plan is not None
    assert report.encoding_plan["symbol"] == "ean13"
    assert report.encoding_plan["tie_break"] == "longest-first"
    assert "module_not_implemented:M2" not in report.skipped
    assert "module_not_implemented:M3" in report.skipped
    assert report.tools["symbol_profiles_version"]
    assert report.tools["symbol_profiles_sha256"]


def test_pipeline_infeasible_symbol_is_a_module_m2_finding():
    report = pipeline.run(_payload(symbol="upca"), {"file": "spec.json"})
    findings = [finding for finding in report.findings if finding.module == "M2"]
    assert [finding.id for finding in findings] == ["symbol_length_mismatch"]
    assert findings[0].fix["to"] == "12"
    assert report.encoding_plan is None
    # 未核规则 → warn，不是 fail（§8.2 同一口径）；--strict-thresholds 才恢复 error。
    assert report.verdict == "warn"
    strict = pipeline.run(
        _payload(symbol="upca"), {"file": "spec.json"}, strict_thresholds=True
    )
    assert strict.verdict == "fail"


def test_pipeline_without_symbol_says_so_instead_of_guessing():
    report = pipeline.run(
        {"schema": "bpreflight/spec/1", "identifier": "09501101530003"},
        {"file": "spec.json"},
    )
    assert "symbol_not_specified" in report.skipped
    assert report.encoding_plan is None
    assert report.verdict == "pass"


def test_pipeline_unparseable_element_string_does_not_invent_a_plan():
    report = pipeline.run(
        _payload(identifier=None, gs1_element_string="(65)nope"),
        {"file": "spec.json"},
    )
    assert "symbol_data_unparsed" in report.skipped
    assert report.encoding_plan is None


def test_report_renders_the_plan_in_both_formats():
    from bpreflight.report import render_json, render_md

    report = pipeline.run(_payload(), {"file": "spec.json"})
    md_text, _ = render_md.render_md(report)
    assert "## Encoding plan" in md_text
    assert "`tie_break`: longest-first" in md_text

    payload = json.loads(render_json.render_json(report)[0])
    assert payload["encoding_plan"]["tie_break"] == "longest-first"
