"""编排层：骨架期的诚实、阈值三态、不可判通道。

这些是"骨架不能靠没有 findings 冒充 pass"与"未核阈值降级"的常驻断言。
M1 落地时 `implementation_pending` 退役，第一条测试要随之改为"不存在"。
"""

import json
import pathlib

import pytest

from bpreflight import pipeline
from bpreflight import thresholds


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


def test_skeleton_never_reports_pass():
    """M0 没有判定层：空 findings 会派生 pass，那是撒谎（决策 D16）。"""
    report = pipeline.run(_payload(), {"file": "spec.json", "sha256": "ab", "mode": "params"})
    assert report.verdict == "fail"
    assert any(f.id == pipeline.PENDING_ID for f in report.findings)


def test_pending_finding_is_an_error_with_actionable_fix():
    report = pipeline.run(_payload(), {"file": "spec.json"})
    pending = [f for f in report.findings if f.id == pipeline.PENDING_ID][0]
    assert pending.severity == "error"
    assert pending.fix["to"]


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
