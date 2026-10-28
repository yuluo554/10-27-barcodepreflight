#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Python 下限门：`src/` / `tests/` / `tools/` 不得出现越过 `requires-python` 下限的语法。

背景（`references/methodology-binding.md` ⑱ 的同族，实测复发率高）：
本项目 `requires-python = ">=3.12"`，但开发机上的解释器可能比下限新，会把新语法
**照单全收**——同一种写法会在仓库里反复复发，CI 的矩阵才第一次红。

**扫描面 = `src/` / `tests/` / `tools/`**（M6.1 收编）：`tools/` 里 7 个脚本同样会在
这台机器上跑，漏掉它就是一个"没有门的门"（D2 实测：往 `tools/` 放 `list[int]` →
该门仍 PASS，而低版本解释器跑该文件是 TypeError）。

两段判据：

  ① **高于下限的语法**（随 `MIN_VERSION` 而动）：用
     `ast.parse(source, feature_version=(3, 12))` 解析；解析不了即"该文件的语法
     需要比下限更新的解释器"。这条把 `MIN_VERSION` 从"只印在标题上的字"变成判据本身。

  ② **保守禁用清单**（比下限更严，历史遗留）：`ast.Match`（3.10）/ 注解位置的
     `X | Y`（3.10）/ 内建泛型注解 `list[int]`（3.9）。这三类在 3.12 下**合法**，
     本门仍禁是因为它们正是本门的由来（每一条都在这台机器上复发过），本代码库
     零使用，保留使 `verify_gates` 的 P1/P2 两组阳性变异仍咬得住东西。
     **这是"比下限更严"，不是放宽**；要解禁请同时改这里与 `tools/verify_gates.py`。

**不扫子串**：注释里写 "3.10 的 match" 不应误红。

退出码：0 无命中 / 1 有命中。
"""

import ast
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_ROOTS = [
    os.path.join(ROOT, "src", "bpreflight"),
    os.path.join(ROOT, "tests"),
    os.path.join(ROOT, "tools"),
]

MIN_VERSION = "3.12"
MIN_FEATURE_VERSION = (3, 12)

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


def _parse_error(source, path):
    """按 `MIN_VERSION` 的语法解析；解析不了就返回一句问题描述。"""
    try:
        ast.parse(source, filename=path, feature_version=MIN_FEATURE_VERSION)
    except SyntaxError as exc:
        return "语法需要比 {} 更新的解释器: {}".format(MIN_VERSION, exc.msg)
    return None


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

    # 0) 高于下限的语法（判据随 MIN_VERSION 而动）
    parse_problem = _parse_error(source, path)
    if parse_problem is not None:
        return [(1, parse_problem)]

    tree = ast.parse(source, filename=path)
    problems = []

    # 1) match 语句（3.10；比下限更严，见模块 docstring ②）
    match_type = getattr(ast, "Match", None)
    if match_type is not None:
        for node in ast.walk(tree):
            if isinstance(node, match_type):
                problems.append((node.lineno, "match 语句（3.10+）"))

    # 2) 注解里的 `X | Y`（3.10；比下限更严，见模块 docstring ②）
    for annotation in _annotation_nodes(tree):
        for node in ast.walk(annotation):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                problems.append((getattr(node, "lineno", 0), "注解里用 `X | Y`（3.10+）"))

    # 3) 内建泛型注解（3.9；比下限更严，见模块 docstring ②）
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
        "PASS  扫描 {} 份 .py，0 处越过 {} 的语法（1 类 AST 解析 + 3 类保守禁用）\n".format(
            scanned, MIN_VERSION
        )
    )
    out.write("=" * 60 + "\n")
    out.write("结论: 全绿\n")
    sys.stdout.write(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
