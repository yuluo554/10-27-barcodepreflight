"""退出码矩阵：§8.5 的 9 格 + 三类 3（`plan/05` M4 DoD）。

M0 就覆盖到 9 格，M4 再加"经 CLI 端到端"的同一矩阵。
"""

import pytest

from bpreflight import exitcodes

FAIL_ONS = ("none", "warn", "error")
WORSTS = ("info", "warn", "error")

EXPECTED = {
    # (fail_on, worst) -> exit
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


@pytest.mark.parametrize("fail_on", FAIL_ONS)
@pytest.mark.parametrize("worst", WORSTS)
def test_exit_matrix_cell(fail_on, worst):
    assert exitcodes.exit_code(fail_on, worst) == EXPECTED[(fail_on, worst)]


def test_matrix_is_nine_cells():
    """分母由构造算出，不是手写常量：漏一格会让这条直接红。"""
    assert len(EXPECTED) == len(FAIL_ONS) * len(WORSTS)


@pytest.mark.parametrize("fail_on", FAIL_ONS)
def test_usage_error_wins_over_any_gate(fail_on):
    """三类 3（用法错误 / 输入不可解析 / 字典缺失）优先于 0/1/2。"""
    assert exitcodes.exit_code(fail_on, "error", usage_error=True) == 3
    assert exitcodes.exit_code(fail_on, "info", usage_error=True) == 3


def test_unknown_fail_on_is_rejected():
    with pytest.raises(ValueError):
        exitcodes.exit_code("bogus", "error")


def test_default_fail_on_is_none():
    """默认只报告不拦（§8.5 设计取舍）——写进 README 首屏。"""
    parser_default = None
    from bpreflight.cli import build_parser

    args = build_parser().parse_args(["check", "--input", "x.json"])
    parser_default = args.fail_on
    assert parser_default == "none"
