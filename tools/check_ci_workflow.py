#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CI 工作流门：`.github/workflows/*.yml` 必须留在**可解析的子集**里。

为什么需要这条（实测背景）：M0 的 `ci.yml` 里有一行

    - name: Smoke (installed CLI: help + example run)

**不是合法 YAML**——未加引号的纯量里出现 `": "` 会被解析成嵌套映射的开始。这份文件
从 M0 到 M1 一直躺在仓库里、谁也跑不到它（`D19`：本轮不建远端），直到 M6 首推时才会在
GitHub 侧炸掉。这正是"门只在开发机存在等于没有"的反面：**文件在 CI 里，但没人判它**。

**为什么不用 PyYAML**：本项目 `src/` 零第三方依赖，`tools/` 也一直只用标准库
（PyYAML 在干净的解释器里不保证存在，装上它等于把门变成"看机器装了什么"）。

**为什么是"fail-closed 子集"而不是"更聪明的解析器"**：判据只认本项目实际用到的构造；
**遇到不认识的形状一律报红**，逼人来决定，而不是猜。这样它不会退化成"看起来在判、其实
在放行"的假门（`references/methodology-binding.md` 假门族 ⑬/⑱）。

判据（每加一条都要在 `tools/verify_gates.py` 里配一组变异）：

  CI.PARSE      逐行形状必须属于可识别子集；纯量里出现未加引号的 `": "` 即红
  CI.GATES      六个门脚本各自**独占一个 step**，且没有任何 step 同时跑两个门（决策 D18）
  CI.MATRIX     `pytest` 矩阵必须含 `requires-python` 下限的实跑腿（下限由
                `pyproject.toml` 算出，不写死）。下限从 3.8 抬到 3.12 后，本判据同步
                改为只认 3.12 —— 这是"下限变了、判据跟着变"的合法口径调整，不是放宽：
                矩阵仍必须含一个实跑的 3.12 腿，且 `pyproject.toml` 的 `requires-python`
                与它必须一致（见 `read_floor`）。

退出码：0 全绿 / 1 有 FAIL。
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW_DIR = os.path.join(ROOT, ".github", "workflows")

#: 门脚本清单（决策 D18：每条必须是独立 step）。
#: M3 加 `gen_fixtures.py`：`--check` 判"fixture 清单与判定行为是否还一致"，
#: 失败模式与其它门相同（该红时必须红），因此同样要求独占一个 step。
#: 注意 `verify_gates.py` 的基线会调它，所以它必须**先**在 CI 里跑过。
GATE_SCRIPTS = (
    "check_sprint_layout.py",
    "check_desensitized.py",
    "check_thresholds.py",
    "check_python_floor.py",
    "check_ci_workflow.py",
    "gen_fixtures.py",
    "verify_gates.py",
)

#: 矩阵里必须实跑的版本 —— **从 `pyproject.toml` 的 `requires-python` 算出**，不写死。
#: 写死会让"下限改了、判据没改"变成假话（M6.1 抬 3.8→3.12 就是这么来的）。
#: 口径：`requires-python = ">=X.Y"` 里的 X.Y 必须有一条矩阵腿实跑。
_FLOOR_RE = re.compile(r'^\s*requires-python\s*=\s*"[><=~! ]*(\d+\.\d+)', re.M)


def read_floor():
    """读 `pyproject.toml` 的 requires-python 下限；读不到返回 None。"""
    path = os.path.join(ROOT, "pyproject.toml")
    if not os.path.isfile(path):
        return None
    with io.open(path, "r", encoding="utf-8") as handle:
        match = _FLOOR_RE.search(handle.read())
    return match.group(1) if match else None


_MATRIX_PY_RE = re.compile(r'^\s*python\s*:\s*"?(\d+\.\d+)"?\s*$', re.M)


def _matrix_pythons(lines):
    """矩阵里实际出现的 python 版本（按出现序去重）。"""
    seen = []
    for value in _MATRIX_PY_RE.findall("\n".join(lines)):
        if value not in seen:
            seen.append(value)
    return seen

_SCRIPT_RE = re.compile(r"tools/([\w.-]+\.py)")
_MAPPING_RE = re.compile(r"^([\w\"'.-]+):(\s|$)(.*)$")
_BLOCK_MARKER_RE = re.compile(r"^[|>][-+0-9]*$")
_KEY_ONLY_RE = re.compile(r"^([\w\"'.-]+):\s*$")


class Problem(object):
    __slots__ = ("check_id", "detail")

    def __init__(self, check_id, detail):
        self.check_id = check_id
        self.detail = detail


def iter_workflows():
    if not os.path.isdir(WORKFLOW_DIR):
        return []
    return [
        os.path.join(WORKFLOW_DIR, name)
        for name in sorted(os.listdir(WORKFLOW_DIR))
        if name.endswith((".yml", ".yaml"))
    ]


def _value_trouble(value, lineno, path):
    """纯量形状检查。返回问题描述或 None。判据只认"必须拒绝"的形状。"""
    if not value:
        return None
    first = value[0]
    if first in "\"'":
        return None  # 加了引号：YAML 的转义由引号负责，不再静态判
    if first in "[{":
        # 流式集合：只判括号配平（不判内部语义，避免假装懂 YAML）
        depth = 0
        for char in value:
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            if depth < 0:
                return "{}:{} 流式集合括号不配平: {}".format(path, lineno, value.strip())
        if depth != 0:
            return "{}:{} 流式集合括号不配平: {}".format(path, lineno, value.strip())
        return None
    if _BLOCK_MARKER_RE.match(value.strip()):
        return None  # 块标量标记（| / >），内容由调用方跳过
    if ": " in value:
        # 这是 M0 真实踩过的那一脚：未加引号的纯量里 `": "` 会开启嵌套映射。
        return (
            "{}:{} 未加引号的纯量里出现 \": \"（会被解析成嵌套映射，必须加引号）: {}".format(
                path, lineno, value.strip()
            )
        )
    if " #" in value:
        return "{}:{} 未加引号的纯量里出现 \" #\"（会被当成注释起点）: {}".format(
            path, lineno, value.strip()
        )
    return None


def check_parse(path):
    """逐行判形状（fail-closed）。返回 (problems, steps) —— steps 供 CI.GATES 用。

    `steps` 是 `[(标题, [run 块的内容行...]), ...]`。
    """
    problems = []
    with io.open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    steps = []
    current_step = None
    block_indent = None  # 正在块标量里时 = 该 key 的缩进 + 1
    index = 0
    while index < len(lines):
        raw = lines[index]
        lineno = index + 1
        index += 1
        stripped = raw.strip()

        if block_indent is not None:
            indent = len(raw) - len(raw.lstrip(" "))
            if stripped and indent < block_indent:
                block_indent = None  # 块标量结束，按普通行继续判
            else:
                if current_step is not None and current_step[1] is not None:
                    current_step[1].append(raw)
                continue

        if not stripped or stripped.startswith("#"):
            continue

        body = stripped
        if body.startswith("- "):
            body = body[2:].strip()
            current_step = [body, None]
            if body.startswith("name:"):
                steps.append(current_step)
            else:
                # `- uses: ...` 这类没有 name 的 step：整条链只放一处，
                # 否则纯量形状问题会漏判（fail-closed 要求逐行都过一遍）。
                steps.append(current_step)
        elif body == "-":
            body = ""

        if not body:
            continue

        match = _MAPPING_RE.match(body)
        if not match:
            if body.startswith("- "):
                continue  # 序列里的裸标量（本文件不用，但形状合法）
            problems.append(
                Problem("CI.PARSE", "{}:{} 无法识别的行形状: {}".format(path, lineno, raw))
            )
            continue

        _key, _spacing, value = match.groups()
        if value is None:
            value = ""
        value = value.rstrip()

        trouble = _value_trouble(value, lineno, path)
        if trouble:
            problems.append(Problem("CI.PARSE", trouble))

        key = _key.strip().strip("\"'")
        if current_step is not None and key == "run":
            if _BLOCK_MARKER_RE.match(value.strip()):
                block_indent = (len(raw) - len(raw.lstrip(" "))) + 1
                current_step[1] = []
            else:
                # 行内 run（单行命令）也要收进来，否则"这个 step 跑了什么"看不见。
                current_step[1] = [value]

    return problems, steps


def check_gates_as_separate_steps(path, steps):
    """决策 D18：五个门各自独占一个 step。"""
    problems = []
    owners = {}
    for title, run_lines in steps:
        if run_lines is None:
            continue
        text = "\n".join(run_lines)
        found = sorted({name for name in _SCRIPT_RE.findall(text) if name in GATE_SCRIPTS})
        if len(found) > 1:
            problems.append(
                Problem(
                    "CI.GATES",
                    "{}: step {!r} 同时跑了多个门（必须各自独立 step）: {}".format(
                        path, title, ",".join(found)
                    ),
                )
            )
        for name in found:
            owners.setdefault(name, []).append(title)

    for name in GATE_SCRIPTS:
        titles = owners.get(name)
        if not titles:
            problems.append(
                Problem("CI.GATES", "{}: 门 {} 没有出现在任何独立 step 里".format(path, name))
            )
        elif len(titles) > 1:
            problems.append(
                Problem(
                    "CI.GATES",
                    "{}: 门 {} 出现在 {} 个 step 里（会跑两遍或语义不清）".format(
                        path, name, len(titles)
                    ),
                )
            )
    return problems


def check_matrix(path, lines, floor):
    """`requires-python` 的下限必须在矩阵里有一条实跑腿。

    `floor` 由 `pyproject.toml` 算出（不写死）：下限抬到 3.12 之后，
    矩阵里"必须有 3.8"就不再成立；但"必须有下限本身的实跑"永远成立。
    """
    if floor is None:
        return [
            Problem("CI.MATRIX", "{}: 读不到 pyproject.toml 的 requires-python，判据无法成立".format(path))
        ]
    present = _matrix_pythons(lines)
    if not present:
        return [Problem("CI.MATRIX", "{}: pytest 矩阵里解析到 0 个 python 版本 —— 判据空跑".format(path))]
    if floor not in present:
        return [
            Problem(
                "CI.MATRIX",
                "{}: pytest 矩阵缺下限 {} 的实跑腿（现有: {}）".format(
                    path, floor, ", ".join(present)
                ),
            )
        ]
    return []


def main():
    problems = []
    out = io.StringIO()
    out.write("CI 工作流门 · 判据 = fail-closed 行形状 + 独立 step + 矩阵版本\n")
    out.write("=" * 60 + "\n")

    workflows = iter_workflows()
    if not workflows:
        out.write("FAIL  扫到 0 份工作流文件 —— 判据空跑\n")
        sys.stdout.write(out.getvalue())
        return 1

    scanned_lines = 0
    steps_seen = 0
    floor = read_floor()
    matrix_versions = []
    for path in workflows:
        with io.open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        scanned_lines += len(lines)
        parse_problems, steps = check_parse(path)
        problems.extend(parse_problems)
        steps_seen += len(steps)
        problems.extend(check_gates_as_separate_steps(path, steps))
        problems.extend(check_matrix(path, lines, floor))
        for version in _matrix_pythons(lines):
            if version not in matrix_versions:
                matrix_versions.append(version)

    # 非空跑自证：门清单里的每条判据都要真的咬过东西
    for name in GATE_SCRIPTS:
        if not any(
            name in io.open(path, "r", encoding="utf-8").read() for path in workflows
        ):
            problems.append(
                Problem("CI.GATES", "门 {} 在工作流里一次都没出现（判据空跑）".format(name))
            )
    if steps_seen == 0:
        problems.append(Problem("CI.GATES", "解析到 0 个 step —— 判据空跑"))

    if problems:
        for problem in problems:
            out.write("FAIL  [{}] {}\n".format(problem.check_id, problem.detail))
        out.write("=" * 60 + "\n")
        out.write(
            "扫描 {} 份工作流 / {} 行 / {} 个 step，命中 {} 处。\n".format(
                len(workflows), scanned_lines, steps_seen, len(problems)
            )
        )
        out.write("结论: FAIL\n")
        sys.stdout.write(out.getvalue())
        return 1

    out.write(
        "PASS  扫描 {} 份工作流 / {} 行 / {} 个 step；{} 个门各自独立 step；"
        "矩阵含 {}（requires-python 下限 {}）；0 处命中\n".format(
            len(workflows),
            scanned_lines,
            steps_seen,
            len(GATE_SCRIPTS),
            "+".join(matrix_versions),
            floor,
        )
    )
    out.write("=" * 60 + "\n")
    out.write("结论: 全绿\n")
    sys.stdout.write(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())