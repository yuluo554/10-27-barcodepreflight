"""M1 校验位：四官方向量 + "只有一个实现"的结构判据。

口径来源：`data/README.md` §8.1（算法）与 §4.2（向量）。`plan/00` K1 写死
`grep -rc "def gs1_check_digit" src/` == 1 —— 那条 grep 就是本文件里的
`test_only_one_check_digit_implementation`，它扫的是 **AST/文本面**，不是"我记得只有一个"。

**向量只存"数据位 + 期望校验位"**（`plan/00` K2）：期望值在这里重新算一遍再比，
不把算出来的完整串当不变量抄进来——否则实现和向量会一起漂。
"""

import pathlib

import pytest

from bpreflight.gs1 import checksum, vectors

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"


def _rel(path):
    """仓库相对路径，统一用 `/`（Windows 上 `str(Path)` 是 `\\`）。"""
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _official_vectors():
    return vectors.checksum_vectors()


def test_four_official_vectors_pass():
    """四个官方向量全 PASS（M1 的第一条硬性验收）。"""
    rows = _official_vectors()
    assert len(rows) >= 4, "官方向量少于 4 条 —— 判据空跑"
    for row in rows:
        digits = row["data_digits"]
        full = row["official_vector"]
        computed = checksum.gs1_check_digit(digits)
        assert computed == full[-1], "{}: computed {} but official vector ends {}".format(
            digits, computed, full[-1]
        )
        assert checksum.gs1_is_valid(full), "{} did not validate".format(full)


def test_the_named_vectors_are_present():
    """点名四条（`plan/05` M1 DoD）必须都在，防止"换了向量也算过"。"""
    official = {row["official_vector"] for row in _official_vectors()}
    for expected in ("02345673", "416000336108", "09501101530003", "4006381333931"):
        assert expected in official, "{} 不在向量集里".format(expected)


def test_negative_vectors_are_rejected():
    """错误校验位必须被拒——只测"对的能过"会让"恒返回 3"也全绿。"""
    rows = vectors.load()["checksum"]["negative"]
    assert rows, "否定向量为空 —— 判据空跑"
    for row in rows:
        assert not checksum.gs1_is_valid(row["string"]), row["string"]


def test_hand_computed_weights_match_data_readme():
    """手算留痕（`data/README.md` §4.2）：和值取模路径必须逐位对上。

    独立复算四个向量的加权和，确认"起始权重按含校验位的全长奇偶"这一条真的成立
    （写成"自右向左"或"6 - W"时这四个和值都会变）。
    """
    expected_sums = {
        # data_digits -> (sum, check)
        "0234567": (57, 3),
        "41600033610": (62, 8),
        "0950110153000": (47, 3),
        "400638133393": (89, 1),
    }
    for digits, (expected_sum, expected_check) in sorted(expected_sums.items()):
        total_length = len(digits) + 1
        first = 3 if total_length % 2 == 0 else 1
        weight = first
        total = 0
        for char in digits:
            total += int(char) * weight
            weight = 4 - weight
        assert total == expected_sum, "{} 的加权和应为 {}，实算 {}".format(
            digits, expected_sum, total
        )
        assert checksum.gs1_check_digit(digits) == str(expected_check)


def test_six_minus_w_implementation_would_fail():
    """把交替权重写成 `6 - W`（历史上真实发生过的错）必须与向量不符。

    这是"向量真的在守"的证明：错误写法在同一批向量上产出不同结果。
    """
    def wrong(digits):
        total_length = len(digits) + 1
        weight = 3 if total_length % 2 == 0 else 1
        total = 0
        for char in digits:
            total += int(char) * weight
            weight = 6 - weight
        return str((10 - total % 10) % 10)

    rows = _official_vectors()
    mismatches = [row["data_digits"] for row in rows if wrong(row["data_digits"]) != row["official_vector"][-1]]
    assert mismatches, "错误写法竟然也全对 —— 说明向量没有区分力"


def test_only_one_check_digit_implementation():
    """`plan/00` K1：全仓只准有一个校验位函数定义。

    两条判据一起用，因为单用一种都会假绿：
      · **AST**：`src/` 里名为 `gs1_check_digit` 的函数定义必须正好 1 个
        （注释里提到这个名字不该红）；
      · **文本**：字符串字面量 `def gs1_check_digit` 的出现次数也必须正好 1
        （这正是 DoD 里那条 `grep -rc`；函数名换个写法藏在别处会在这里露出来）。
    0 是空跑，2 是"两套算法并存"。
    """
    import ast

    definitions = []
    text_hits = []
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        rel = _rel(path)
        source = path.read_text(encoding="utf-8")
        text_hits.append((rel, source.count("def gs1_check_digit")))
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "gs1_check_digit":
                definitions.append(rel)

    assert definitions, "src/ 里找不到 gs1_check_digit 定义 —— 判据空跑"
    assert len(definitions) == 1, "校验位实现必须唯一，AST 扫到 {}".format(definitions)
    assert definitions[0] == "src/bpreflight/gs1/checksum.py", (
        "唯一实现必须落在 src/bpreflight/gs1/checksum.py，实际在 {}".format(definitions[0])
    )

    total = sum(count for _, count in text_hits)
    assert total == 1, "校验位实现必须唯一，文本面实扫 {} 处: {}".format(
        total, [item for item in text_hits if item[1]]
    )


def test_no_fallback_branch_in_checksum_module():
    """不实现"另一种流派"：模块里不许出现第二条候选权重路径（`data/README.md` §8.1）。

    判据取**代码**（AST 数值常量 + 代码正文），不扫注释——错误写法的说明文字
    本来就该写在文档里。
    """
    import ast

    source = (SRC / "bpreflight" / "gs1" / "checksum.py").read_text(encoding="utf-8")

    # 权重表只准定义一次，且必须是 (3, 1)：出现第二处定义就是"两套算法并存"的开端。
    assert "_WEIGHTS = (3, 1)" in source
    assert source.count("_WEIGHTS = ") == 1

    # 代码里除 3/4/10 之外不出现别的权重候选（6 是最常见的那种错写法）。
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            first = getattr(node, "body", [None])[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    numeric = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and id(node) not in docstrings
    ]
    assert 6 not in numeric, "校验位代码里出现 6 —— 是不是又把交替权重写成 6 - W？"


def test_non_digit_input_is_refused_not_guessed():
    """非数字输入要拒绝：对垃圾算校验位比拒绝更糟。"""
    for bad in ("", "12a45", "12 45", "１２３"):
        with pytest.raises(ValueError):
            checksum.gs1_check_digit(bad)


def test_too_short_is_invalid_not_checked():
    assert checksum.gs1_is_valid("7") is False


def test_is_valid_uses_the_same_function():
    """`gs1_is_valid` 必须走同一条算法（防"验证走旁路"）。"""
    for row in _official_vectors():
        full = row["official_vector"]
        assert checksum.gs1_is_valid(full) is True
        wrong = full[:-1] + str((int(full[-1]) + 1) % 10)
        assert checksum.gs1_is_valid(wrong) is False, wrong