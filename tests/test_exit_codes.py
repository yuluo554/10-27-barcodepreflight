"""退出码矩阵：`data/README.md` §8.5 的 9 格 + 三类 3（`plan/05` M4 DoD）。

**逐格一条测试**（不用 parametrize 把 9 格压成 3 条）：`--fail-on ∈ {none, warn,
error}` × `worst ∈ {info, warn, error}`。四条关键格（`none×error`、`warn×warn`、
`error×error`、`warn×info`）另有显式断言。

三类 `3`（用法错误 / 输入不可解析 / 内嵌字典缺失）各一条，且都从真实入口触发：
`3` 优先于 0/1/2，且不参与判定计数。矩阵同时有"纯函数"与"经 CLI 端到端"两条路径。
"""

import pytest

from bpreflight import exitcodes
from bpreflight.cli import main

FAIL_ONS = ("none", "warn", "error")
WORSTS = ("info", "warn", "error")

EXPECTED = {
    ("none", "info"): 0,
    ("none", "warn"): 0,
    ("none", "error"): 0,
    ("warn", "info"): 0,
    ("warn", "warn"): 1,
    ("warn", "error"): 2,
    ("error", "info"): 0,
    ("error", "warn"): 0,
    ("error", "error"): 2,
}


def _spec(tmp_path, **payload):
    """把一份 spec 写进临时文件，返回路径（内容确定性由 sort_keys 保证）。"""
    import json

    base = {"schema": "bpreflight/spec/1"}
    base.update(payload)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(base, sort_keys=True), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# 纯函数：9 格逐格一条
# --------------------------------------------------------------------------- #


def test_none_info_is_zero():
    assert exitcodes.exit_code("none", "info") == 0


def test_none_warn_is_zero():
    assert exitcodes.exit_code("none", "warn") == 0


def test_none_error_is_zero():
    assert exitcodes.exit_code("none", "error") == 0


def test_warn_info_is_zero():
    assert exitcodes.exit_code("warn", "info") == 0


def test_warn_warn_is_one():
    assert exitcodes.exit_code("warn", "warn") == 1


def test_warn_error_is_two():
    assert exitcodes.exit_code("warn", "error") == 2


def test_error_info_is_zero():
    assert exitcodes.exit_code("error", "info") == 0


def test_error_warn_is_zero():
    assert exitcodes.exit_code("error", "warn") == 0


def test_error_error_is_two():
    assert exitcodes.exit_code("error", "error") == 2


def test_matrix_is_nine_cells():
    """分母由构造算出：漏一格会让这条直接红。"""
    assert len(EXPECTED) == len(FAIL_ONS) * len(WORSTS)
    assert set(EXPECTED) == {(f, w) for f in FAIL_ONS for w in WORSTS}


def test_key_cells_are_pinned_explicitly():
    """四条关键格显式断言（`plan/01` §M4）：默认不拦 / 门槛随最严重级别。"""
    assert exitcodes.exit_code("none", "error") == 0   # 默认只报告不拦
    assert exitcodes.exit_code("warn", "warn") == 1    # 跨 warn 门槛
    assert exitcodes.exit_code("error", "error") == 2  # 跨 error 门槛
    assert exitcodes.exit_code("warn", "info") == 0    # info 不跨任何门槛


# --------------------------------------------------------------------------- #
# 三类 3（用法错误 / 输入不可解析 / 内嵌字典缺失）：优先且不参与计数
# --------------------------------------------------------------------------- #


def test_usage_error_wins_over_any_gate():
    """用法错误覆盖一切：即使 worst=info（本应 0）也必须 3。"""
    for fail_on in FAIL_ONS:
        assert exitcodes.exit_code(fail_on, "info", usage_error=True) == 3
        assert exitcodes.exit_code(fail_on, "error", usage_error=True) == 3


def test_unknown_fail_on_is_rejected():
    with pytest.raises(ValueError):
        exitcodes.exit_code("bogus", "error")


def test_default_fail_on_is_none():
    """默认只报告不拦（§8.5 设计取舍）——写进 README 首屏。"""
    from bpreflight.cli import build_parser

    args = build_parser().parse_args(["check", "--input", "x.json"])
    assert args.fail_on == "none"


def test_unparseable_input_returns_three(tmp_path, capsys):
    """输入不可解析（非法 JSON）→ exit 3。"""
    path = tmp_path / "spec.json"
    path.write_text("{not json", encoding="utf-8")
    code = main(["check", "--input", str(path)])
    assert code == 3
    assert "not valid JSON" in capsys.readouterr().err


def test_missing_dictionary_returns_three(tmp_path, monkeypatch, capsys):
    """内嵌字典缺失 / 摘要不符 → exit 3，且不产任何领域结论。"""
    from bpreflight.gs1 import dictionary

    def _boom(*args, **kwargs):
        raise dictionary.DictionaryError("bundled dictionary digest mismatch")

    # pipeline 通过 `dictionary` 模块对象调用 `load`，patch 模块属性即覆盖它。
    monkeypatch.setattr(dictionary, "load", _boom)
    path = _spec(tmp_path, gs1_element_string="(01)09501101530003")
    code = main(["check", "--input", str(path)])
    assert code == 3
    assert "digest mismatch" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# 端到端：同一矩阵经真实 CLI（spec → verdict → 退出码）
# --------------------------------------------------------------------------- #


def _cli_exit(tmp_path, capsys, payload, fail_on):
    path = _spec(tmp_path, **payload)
    return main(["check", "--input", str(path), "--fail-on", fail_on])


#: 三种最严重级别的确定性 spec（结论已由 `pipeline.run` 复算）。
_INFO_SPEC = {"gs1_element_string": "(01)09501101530003(17)251200"}
_WARN_SPEC = {
    "symbol": "ean13",
    "x_dimension_mm": "0.330",
    "target_dpi": 300,
    "quiet_zone_mm": {"left": "0.6", "right": "0.6", "top": "0", "bottom": "0"},
}
_ERROR_SPEC = {
    "symbol": "code128",
    "x_dimension_mm": "0.330",
    "target_dpi": 300,
    "quiet_zone_mm": "0",
}


def test_cli_info_spec_cells(tmp_path, capsys):
    assert _cli_exit(tmp_path, capsys, _INFO_SPEC, "none") == 0
    assert _cli_exit(tmp_path, capsys, _INFO_SPEC, "warn") == 0
    assert _cli_exit(tmp_path, capsys, _INFO_SPEC, "error") == 0


def test_cli_warn_spec_cells(tmp_path, capsys):
    assert _cli_exit(tmp_path, capsys, _WARN_SPEC, "none") == 0
    assert _cli_exit(tmp_path, capsys, _WARN_SPEC, "warn") == 1
    assert _cli_exit(tmp_path, capsys, _WARN_SPEC, "error") == 0


def test_cli_error_spec_cells(tmp_path, capsys):
    assert _cli_exit(tmp_path, capsys, _ERROR_SPEC, "none") == 0
    assert _cli_exit(tmp_path, capsys, _ERROR_SPEC, "warn") == 2
    assert _cli_exit(tmp_path, capsys, _ERROR_SPEC, "error") == 2