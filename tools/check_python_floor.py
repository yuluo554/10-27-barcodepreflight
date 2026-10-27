#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Python 下限门：`src/` 与 `tests/` 不得出现越过 `requires-python` 下限的语法。

背景（`references/methodology-binding.md` ⑱ 的同族，实测复发率高）：
本项目 `requires-python = ">=3.8"`，但开发机上的 `py -3.12` 会把 3.9+/3.10+ 语法
**照单全收**——同一个 3.10 泛型注解会在测试里反复复发，CI 的 3.8 矩阵才第一次红。

判据取 **AST**，不是字符串：
  · `ast.Match`（3.10 的 `match`）—— 3.8 的 `ast` 里没有这个名字，所以按"存在性"判；
  · `BinOp` 里 `X | Y` 用在**注解位置**（`ast.Subscript` 的切片是 `ast.BinOp(BitOr)`）—— 3.10 的 `X | Y`；
  · 内建泛型注解 `list[int]` / `dict[str, int]` / `tuple[...]` / `set[...]`（3.9+）——
    在 `AnnAssign` / `arg.annotation` / `FunctionDef.returns` 位置出现 `ast.Subscript` 且
    `value` 是内建名；
  · `ast.NamedExpr` 允许（3.8 已有）；`ast.Constant` 允许。

**不扫子串**：注释里写 "3.10 的 match" 不应误红。

退出码：0 无命中 / 1 有命中。
"""

import ast
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_ROOTS = [os.path.join(ROOT, "src", "bpreflight"), os.path.join(ROOT, "tests")]

MIN_VERSION = "3.8"

BUILTIN_GENERIC_NAMES = {"list", "dict", "tuple", "set", "frozenset", "type"}


def iter_py_files():
    total = 0
    for base in SCAN_ROOTS:
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for name in sorted(filenames):
                if name.endswith(".py"):
                    total += 1
                    yield os.path.join(dirpath, name)
    if total == 0:
        yield None


def _annotation_nodes(tree):
    """所有处于"注解位置"的节点。"""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            found.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                if arg.annotation is not None:
                    found.append(arg.annotation)
            if getattr(node.args, "vararg", None) and node.args.vararg.annotation:
                found.append(node.args.vararg.annotation)
            if getattr(node.args, "kwarg", None) and node.args.kwarg.annotation:
                found.append(node.args.kwarg.annotation)
            if node.returns is not None:
                found.append(node.returns)
    return found


def violations(path):
    with io.open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source, filename=path)
    problems = []

    # 1) match 语句（3.10）
    match_type = getattr(ast, "Match", None)
    if match_type is not None:
        for node in ast.walk(tree):
            if isinstance(node, match_type):
                problems.append((node.lineno, "match 语句（3.10+）"))

    # 2) 注解里的 `X | Y`（3.10）
    for annotation in _annotation_nodes(tree):
        for node in ast.walk(annotation):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                problems.append((getattr(node, "lineno", 0), "注解里用 `X | Y`（3.10+）"))

    # 3) 内建泛型注解（3.9）
    for annotation in _annotation_nodes(tree):
        for node in ast.walk(annotation):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                if node.value.id in BUILTIN_GENERIC_NAMES:
                    problems.append(
                        (getattr(node, "lineno", 0), "内建泛型注解 `{}[...]`（3.9+）".format(node.value.id))
                    )

    return problems


def main():
    out = io.StringIO()
    out.write("Python 下限门（requires-python >= {}） · 判据 = AST\n".format(MIN_VERSION))
    out.write("=" * 60 + "\n")
    hits = []
    scanned = 0
    for path in iter_py_files():
        if path is None:
            out.write("FAIL  扫到 0 个 .py 文件 —— 判据空跑\n")
            sys.stdout.write(out.getvalue())
            return 1
        scanned += 1
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        for lineno, what in violations(path):
            hits.append((rel, lineno, what))

    if hits:
        for rel, lineno, what in hits:
            out.write("FAIL  {}:{}  {}\n".format(rel, lineno, what))
        out.write("=" * 60 + "\n")
        out.write("扫描 {} 份 .py，命中 {} 处。\n".format(scanned, len(hits)))
        out.write("结论: FAIL\n")
        sys.stdout.write(out.getvalue())
        return 1

    out.write(
        "PASS  扫描 {} 份 .py，0 处越过 3.8 的语法（3 类判据）\n".format(scanned)
    )
    out.write("=" * 60 + "\n")
    out.write("结论: 全绿\n")
    sys.stdout.write(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
