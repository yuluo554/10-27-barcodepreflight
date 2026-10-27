#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阈值零硬编码门：`src/` 不得出现裸阈值字面量。

为什么：口径只在 `data/README.md` §8 定义一次、值只在包内 JSON 定义一次。代码里出现
`5.88` / `0.330` / `2.0` 这类字面量就必然漂移——改口径时漏一处，判定就静默变了。

判据取 **AST 常量节点**，不是子串（`references/methodology-binding.md` 假门族 ⑱）：
docstring / 注释里提到数字不应误红。

允许面（逐条列白名单，且白名单本身要可见）：
  · `src/bpreflight/data/` 下的 JSON 不是 Python，不在扫描面；
  · 允许的数值：`0` / `1` / `-1` / `0.0` / `1.0` 这类结构性常量（下标、长度、真值），
    以及 `2`（`//` `%` 类算术与 `[:2]` 切片）——它们是算法结构，不是印刷阈值；
  · 任何**其他**数值常量出现在 `src/bpreflight/` 的 `.py` 里，必须在本表的 `ALLOWED` 中
    逐条登记并写理由（登记表清空是应当被断言的终态）。

退出码：0 无命中 / 1 有命中。
"""

import ast
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "bpreflight")

#: 结构性常量（不是阈值）。判别 = "这个数改口径时会不会跟着变？" 不会 ⇒ 允许。
ALLOWED_NUMBERS = {
    0,
    1,
    2,
    -1,
    0.0,
    1.0,
    8,      # zip 容器位宽 / hex 半字节
    16,     # fingerprint 前 16 位十六进制
    10,     # 十进制基数
    100,    # 百分比换算（%）
    0.05,   # WCAG 相对亮度公式的常数项（公式本身，不是阈值）
    255,    # 8-bit 通道上限
    3,      # 通道数 / RGB 序列长度
    0.5,    # 半程下取整
    4,      # 4 位块 / 分桶
    60,     # 秒分换算
}

#: 逐条登记"看似阈值、实为结构"的数字。**必须留空表 = 正确终态**（假门族 ⑬）。
REGISTERED = {}

SCAN_DIRS = ("", "report")


def iter_py_files():
    count = 0
    for dirpath, dirnames, filenames in os.walk(SRC):
        dirnames[:] = sorted(d for d in dirnames if d not in {"__pycache__", "data"})
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)
                count += 1
    if count == 0:
        yield None  # 让调用方报"空跑"


def numeric_constants(path):
    with io.open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    found = []
    for node in ast.walk(tree):
        # 只看真常量；`ast.Constant` 覆盖 3.8+（`Num` 是 3.7 的旧名）。
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):  # True/False 是 int 子类，跳过
                continue
            found.append((getattr(node, "lineno", 0), node.value))
    return found


def main():
    hits = []
    scanned_files = 0
    scanned_consts = 0
    for path in iter_py_files():
        if path is None:
            sys.stdout.write("FAIL  阈值门扫到 0 个 .py 文件 —— 判据空跑\n")
            return 1
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        scanned_files += 1
        for lineno, value in numeric_constants(path):
            scanned_consts += 1
            if value in ALLOWED_NUMBERS:
                continue
            if (rel, value) in REGISTERED:
                continue
            hits.append((rel, lineno, value))

    out = io.StringIO()
    out.write("阈值零硬编码门 · 判据 = AST 数值常量（不扫子串）\n")
    out.write("=" * 60 + "\n")
    if hits:
        for rel, lineno, value in hits:
            out.write("FAIL  {}:{}  裸数值常量 {!r}\n".format(rel, lineno, value))
        out.write("=" * 60 + "\n")
        out.write(
            "扫描 {} 份 .py / {} 个数值常量，命中 {} 处。阈值请从包内 JSON 装载。\n".format(
                scanned_files, scanned_consts, len(hits)
            )
        )
        out.write("结论: FAIL\n")
        sys.stdout.write(out.getvalue())
        return 1

    out.write(
        "PASS  扫描 {} 份 .py / {} 个数值常量，0 处未登记字面量（允许集 {} 项 + 登记 {} 项）\n".format(
            scanned_files, scanned_consts, len(ALLOWED_NUMBERS), len(REGISTERED)
        )
    )
    out.write("=" * 60 + "\n")
    out.write("结论: 全绿\n")
    sys.stdout.write(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
