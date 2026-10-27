"""编排层：判定层的诚实（退役后仍然成立）、阈值三态、不可判通道。

M1 落地时 `implementation_pending` 退役（`plan/00` D17 的到期条款）。退役**不是**
把两条测试删掉，而是换成两条更强的：①那个 id 全仓不再出现；②`pass` 只在真有判定
发生时可能出现——没有判定时必须是 `input_incomplete`(error) 或 `skipped`。
"""

import json
import pathlib

import pytest

from bpreflight import pipeline
from bpreflight import thresholds


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: M0 骨架用的占位判定 id。M1 同提交退役——**这个名字不该再出现**（见下）。
RETIRED_PENDING_ID = "implementation_pending"


def _payload(**overrides):
    base = {
        "schema": "bpreflight/spec/1",
        "mode": "params",
        "symbol": "ean13",
        "x_dimension_mm": "0.330",
        "target_dpi": 300,
        "quiet_zone_mm": {"left": "3.63", "right": "2.31", "top": "0", "bottom": "0"},
        "bar_height_mm": "22.85",
        "bar_color": "#000000",
        "space_color": "#FFFFFF",
        "illumination": "red",
    }
    base.update(overrides)
    return base


def _clean_payload():
    """一条语法与校验位都干净的 GS1 元素串：M1 真判过且判没问题。"""
    return {"schema": "bpreflight/spec/1", "gs1_element_string": "(01)09501101530003"}


def test_pending_finding_is_retired():
    """M1 落地：`implementation_pending` 必须消失，而且不能再从任何入口冒出来。"""
    report = pipeline.run(_payload(), {"file": "spec.json", "sha256": "ab"})
    assert not any(f.id == RETIRED_PENDING_ID for f in report.findings)
    report = pipeline.run(_clean_payload(), {"file": "spec.json"})
    assert not any(f.id == RETIRED_PENDING_ID for f in report.findings)

    # 源码面也扫一遍：退役的 id 不许作为**字符串字面量**继续躺在 src/ 里
    # （"改个名字接着用"是最常见的假退役）。判据走 AST 常量，注释与文档
    # 里提到这个名字是允许的——那正是在记录它已经退役。
    import ast

    literals = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == RETIRED_PENDING_ID:
                literals.append("{}:{}".format(path.relative_to(REPO_ROOT), node.lineno))
    assert literals == [], "退役的 id 仍作为字符串字面量存在: {}".format(literals)


def test_pass_only_with_a_real_judgement():
    """两条一起才成立：没判定 ⇒ 不 pass；真判过且干净 ⇒ 允许 pass。"""
    # (1) 输入里没有任何可判的数据面 → 必须 error: input_incomplete，绝不 pass。
    blind = pipeline.run({"schema": "bpreflight/spec/1"}, {"file": "spec.json"})
    assert blind.verdict != "pass"
    incomplete = [f for f in blind.findings if f.id == "input_incomplete"]
    assert incomplete, "缺数据面时必须产 input_incomplete，而不是靠空 findings 冒充 pass"
    assert incomplete[0].severity == "error"
    joined = incomplete[0].observed
    for field in ("gs1_element_string", "identifier"):
        assert field in joined, "input_incomplete 必须点名缺哪个字段（G3）"

    # (2) 真有判定（M1 判过一条干净的元素串）→ pass 是允许的。
    clean = pipeline.run(_clean_payload(), {"file": "spec.json"})
    assert clean.findings == ()
    assert clean.verdict == "pass"


def test_input_incomplete_finding_has_actionable_fix():
    """G3 的 error 也要给可执行修复（决策 D9 不因模块不同而放宽）。"""
    blind = pipeline.run({"schema": "bpreflight/spec/1"}, {"file": "spec.json"})
    finding = [f for f in blind.findings if f.id == "input_incomplete"][0]
    assert finding.severity == "error"
    assert finding.fix["to"]
    assert finding.fix["unit"]


def test_unimplemented_modules_are_announced_not_silent():
    """M2/M3 未落地：报告必须把这件事标出来（`skipped`），不能让人读成"全都判过了"。"""
    report = pipeline.run(_payload(), {"file": "spec.json"})
    assert "module_not_implemented:M2" in report.skipped
    assert "module_not_implemented:M3" in report.skipped


def test_reference_engine_absence_is_declared():
    """`plan/05` M1 DoD：没交给官方 gs1-syntax-engine 对照过，就如实登记。"""
    report = pipeline.run(_clean_payload(), {"file": "spec.json"})
    assert "reference_engine_absent" in report.skipped


def test_thresholds_and_dictionary_identity_are_in_the_report_header():
    """报告头带 `dict_version` / `dict_sha256`，且 sha256 可独立复算。"""
    import hashlib

    from bpreflight.gs1 import dictionary

    report = pipeline.run(_clean_payload(), {"file": "spec.json"})
    assert report.tools["dict_version"]
    manifest = dictionary.load_manifest()
    with open(dictionary.dictionary_path(manifest), "rb") as handle:
        recomputed = hashlib.sha256(handle.read()).hexdigest()
    assert report.tools["dict_sha256"] == recomputed
    assert report.tools["dict_version"] == manifest["dict_version"]


def test_unverified_thresholds_are_surfaced_in_first_screen():
    report = pipeline.run(_payload(), {"file": "spec.json"})
    assert any(w.startswith("THRESHOLDS: unverified") for w in report.warnings)


def test_strict_thresholds_warning_is_explicit():
    report = pipeline.run(_payload(), {"file": "spec.json"}, strict_thresholds=True)
    assert report.strict_thresholds is True
    assert any(w.startswith("THRESHOLDS: unverified") for w in report.warnings)


def test_missing_m3_params_are_skipped_not_defaulted():
    """§8.9 G3：缺参数不静默补默认值，登记为 skipped。"""
    payload = {"schema": "bpreflight/spec/1", "symbol": "ean13"}
    report = pipeline.run(payload, {"file": "spec.json"})
    assert any(s.startswith("input_incomplete:") for s in report.skipped)
    joined = ",".join(report.skipped)
    assert "x_dimension_mm" in joined and "quiet_zone_mm" in joined


def test_report_is_deterministic_across_two_runs():
    first = pipeline.run(_payload(), {"file": "spec.json", "sha256": "ab"})
    second = pipeline.run(_payload(), {"file": "spec.json", "sha256": "ab"})
    assert first.to_dict() == second.to_dict()


def test_with_timestamp_marks_non_deterministic():
    report = pipeline.run(_payload(), {"file": "spec.json"}, with_timestamp=True)
    assert report.deterministic is False


# --------------------------------------------------------------------------- #
# 阈值三态：把 status 在 unverified <-> verified 之间切换，severity 必须对应变化
# --------------------------------------------------------------------------- #


def _patched_book(tmp_path, status, verified_at):
    """复制包内向量到一个临时目录，改一项 status，返回 ThresholdBook。"""
    book = thresholds.load_book()
    quiet = json.loads(json.dumps(book.quiet_zone))
    quiet["symbols"]["ean13"]["left"]["status"] = status
    quiet["symbols"]["ean13"]["left"]["verified_at"] = verified_at
    return thresholds.ThresholdBook(quiet, book.gen_spec, book.sha256)


def test_downgrade_rule_is_a_single_place():
    """降级只看 status 的取值：unverified 的项在 unverified_keys() 里可见。"""
    book = thresholds.load_book()
    assert "quiet_zone.ean13.left" in book.unverified_keys()


def test_verified_entry_is_not_listed_as_unverified(tmp_path):
    book = _patched_book(tmp_path, "verified", "2026-10-27")
    assert "quiet_zone.ean13.left" not in book.unverified_keys()


def test_engineered_entry_status_is_not_applicable():
    """engineering-heuristic 项恒 not-applicable，不参与降级（§8.2 末条）。"""
    book = thresholds.load_book()
    entry = book.engineering("dots_per_module")
    assert book.status_of(entry) == "not-applicable"


def test_gen_spec_entry_status_is_passed_through():
    book = thresholds.load_book()
    entry = book.gen_spec_entry("nominal_x_mm")
    assert book.status_of(entry) in ("verified", "unverified")


# --------------------------------------------------------------------------- #
# 阈值装载的拒绝面（失败路径不静默）
# --------------------------------------------------------------------------- #


def test_verified_without_verified_at_is_rejected():
    with pytest.raises(thresholds.ThresholdError):
        thresholds._validate_gen_spec_item(
            "demo",
            {"source": "x", "status": "verified", "verified_at": None, "basis": "gen-spec"},
        )


def test_unverified_with_verified_at_is_rejected():
    with pytest.raises(thresholds.ThresholdError):
        thresholds._validate_gen_spec_item(
            "demo",
            {
                "source": "x",
                "status": "unverified",
                "verified_at": "2026-10-27",
                "basis": "gen-spec",
            },
        )


def test_missing_source_is_rejected():
    with pytest.raises(thresholds.ThresholdError):
        thresholds._validate_gen_spec_item(
            "demo",
            {"status": "unverified", "verified_at": None, "basis": "gen-spec"},
        )


def test_explicit_threshold_dir_does_not_silently_fall_back(tmp_path):
    """决策：显式给了目录就只认它，无效即报错且明写"不回退"。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(thresholds.ThresholdError) as excinfo:
        thresholds.find_book(str(empty))
    assert "fall back" in str(excinfo.value)
