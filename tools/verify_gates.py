#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""门自检：逐条注入缺陷 → 该门必须变红 → 还原后必须复绿。

为什么必须有这一条（`references/methodology-binding.md` 链三 / 假门族）：
"门跑了且绿"不等于"门里每条判据都被证伪过一次"。本项目首版布局门就在 6 组变异里
4 组没红——那不是"运气好"，是判据根本没咬住东西。

判据格式：每组变异声明 `(gate, mutate, expect_red, label)`：
  · `mutate` 在**仓库的临时副本**上改文件（绝不改工作树）；
  · 每步都断言"字节真的变了"（否则变异退化成 no-op 时会静默变绿）；
  · 期望结果分两类：`expect_red=True`（该判据被抓）与 `expect_red=False`（阴性对照，
    证明该放行的确实放行了 —— 只测"该红的红了"会把判据改死）。

运行：`py -3.12 tools/verify_gates.py`（退出码 0 = 全部符合预期）
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

GATES = {
    "layout": "tools/check_sprint_layout.py",
    "desens": "tools/check_desensitized.py",
    "thresholds": "tools/check_thresholds.py",
    "floor": "tools/check_python_floor.py",
}

IGNORE = shutil.ignore_patterns(
    ".git", ".mimosa", ".claude", ".zcode", "__pycache__", ".pytest_cache", "out", "build", "dist"
)

PLAN00 = "plan/00-README总览.md"
PLAN05 = "plan/05-里程碑与发布.md"
README = "README.md"
PLAN06 = "plan/06-交付对标与决策.md"


# --------------------------------------------------------------------------- #
# 辅助
# --------------------------------------------------------------------------- #


class Mutator(object):
    def __init__(self, root):
        self.root = root

    def path(self, rel):
        return os.path.join(self.root, rel)

    def read(self, rel):
        with io.open(self.path(rel), "r", encoding="utf-8") as handle:
            return handle.read()

    def write(self, rel, text):
        with io.open(self.path(rel), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def replace(self, rel, old, new, count=1):
        """替换并断言字节真的变了。"""
        text = self.read(rel)
        assert old in text, "变异靶子不存在于 {}: {!r}".format(rel, old[:60])
        updated = text.replace(old, new, count)
        assert updated != text, "变异没有产生字节变化：{}".format(rel)
        self.write(rel, updated)

    def append(self, rel, extra):
        text = self.read(rel)
        self.write(rel, text + extra)

    def delete(self, rel):
        target = self.path(rel)
        assert os.path.isfile(target), "变异靶子不存在: {}".format(rel)
        os.remove(target)

    def write_new(self, rel, text):
        target = self.path(rel)
        os.makedirs(os.path.dirname(target) or self.root, exist_ok=True)
        with io.open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def set_status(self, copies, milestone, from_token, to_token):
        """把某里程碑在给定副本里的状态改掉（只改表格行）。"""
        changed = 0
        for rel in copies:
            text = self.read(rel)
            out_lines = []
            for line in text.splitlines(True):
                stripped = line.lstrip()
                if stripped.startswith("|") and "M{}".format(milestone) in line and from_token in line:
                    line = line.replace(from_token, to_token, 1)
                    changed += 1
                out_lines.append(line)
            self.write(rel, "".join(out_lines))
        assert changed > 0, "找不到 M{} 的 {} 状态行".format(milestone, from_token)


def run_gate(root, gate):
    script = os.path.join(root, GATES[gate])
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [PY, "-X", "utf8", script],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# 变异组
# --------------------------------------------------------------------------- #


def m_layout_files(m):
    m.delete("AGENTS.md")


def m_layout_binding(m):
    text = m.read(PLAN00)
    lines = text.splitlines(True)
    kept = [line for line in lines if not line.startswith("> 方法论：")]
    assert len(kept) < len(lines), "装订行不存在"
    m.write(PLAN00, "".join(kept))


def m_layout_sections(m):
    """删掉一个小节**标题**（关键词不能只在正文里出现）。"""
    m.replace("plan/04-数据计划.md", "## 二、真值纪律（本项目四条）", "## 二、纪律")


def m_layout_status(m):
    """两态探测：有待办行 → 翻成 ✅；全已完成 → 翻回 ⬜（靶子与进度无关）。"""
    status_text = m.read(PLAN05)
    pending = [
        line
        for line in status_text.splitlines()
        if line.lstrip().startswith("|") and "M" in line and "⬜" in line
    ]
    if pending:
        m.set_status([PLAN05], 1, "⬜", "✅")
    else:
        m.set_status([PLAN05], 0, "✅", "⬜")


def m_layout_handoffs(m):
    """挑一个**没有**交接单的 ⬜ 里程碑，在三处副本里全标 ✅ → 必须要求 HANDOFF 而它不存在。

    靶子由构造算出，不写死里程碑号：写死 M1 会在 M1 的交接单落盘后失效
    （`references/methodology-binding.md` 假门族 ⑭「靶子过期」的同族）。
    """
    candidates = []
    for milestone in range(1, 10):
        if os.path.isfile(m.path("plan/HANDOFF-M{}.md".format(milestone))):
            continue
        text = m.read(PLAN05)
        if any(
            line.lstrip().startswith("|")
            and "M{}".format(milestone) in line
            and "⬜" in line
            for line in text.splitlines()
        ):
            candidates.append(milestone)
    assert candidates, "找不到任何'没有交接单的待办里程碑'（项目已全部完成？）"
    milestone = candidates[0]

    changed = 0
    for rel in (PLAN00, PLAN05, README):
        text = m.read(rel)
        lines = []
        for line in text.splitlines(True):
            stripped = line.lstrip()
            if stripped.startswith("|") and "M{}".format(milestone) in line and "⬜" in line:
                line = line.replace("⬜", "✅", 1)
                changed += 1
            lines.append(line)
        m.write(rel, "".join(lines))
    assert changed > 0, "M{} 的 ⬜ 行一处都没改到".format(milestone)


def m_layout_gaps(m):
    m.replace(
        PLAN06,
        "| 五模块判定层实现 | 交付面主体 |",
        "| 五模块判定层实现（M0 未完成） | 交付面主体 |",
    )


def m_layout_gaps_file_ref(m):
    """阴性对照：缺口格里点名文件名必须**放行**（⑥ 的反向）。"""
    m.replace(
        PLAN06,
        "| 五模块判定层实现 | 交付面主体 |",
        "| 五模块判定层实现（见 `plan/RELEASE-M6.md`） | 交付面主体 |",
    )


def m_layout_ledger(m):
    m.replace(
        PLAN00,
        "| 校验位手算留痕可复核 | `data/README.md` §4.2 | 文档 | 逐行手算复现 | ✅（文档已落盘） |",
        "| 校验位手算留痕可复核 | `data/README.md` §4.2 | 文档 | 逐行手算复现 | ⬜ 待 M0 复核 |",
    )


def _write_complete_handoff(m, milestone):
    """写一份七节齐的交接单（让"发布留档"判据成为唯一变量）。"""
    body = "# HANDOFF-M{}\n\n".format(milestone) + "".join(
        "## {}\n\n- x\n\n".format(section)
        for section in ("当前进度", "当前事实·状态不变量", "待办", "既定口径", "环境坑", "DoD", "命令速查")
    )
    m.write_new("plan/HANDOFF-M{}.md".format(milestone), body)


def m_layout_release_activation(m):
    """激活即证伪：把 M6 在三处副本里标 ✅，发布留档却不存在 → LAYOUT.RELEASE 必须红。"""
    for rel in (PLAN00, PLAN05, README):
        text = m.read(rel)
        lines = []
        for line in text.splitlines(True):
            stripped = line.lstrip()
            if stripped.startswith("|") and "M6" in line and "⬜" in line:
                line = line.replace("⬜", "✅", 1)
            lines.append(line)
        m.write(rel, "".join(lines))
    _write_complete_handoff(m, 6)


def m_layout_release_two_columns(m):
    """发布留档两栏判据：把 M6 标 ✅ 且给出留档，但删掉"tag 后追加"栏。"""
    for rel in (PLAN00, PLAN05, README):
        text = m.read(rel)
        lines = []
        for line in text.splitlines(True):
            stripped = line.lstrip()
            if stripped.startswith("|") and "M6" in line and "⬜" in line:
                line = line.replace("⬜", "✅", 1)
            lines.append(line)
        m.write(rel, "".join(lines))
    _write_complete_handoff(m, 6)
    m.write_new(
        "plan/RELEASE-M6.md",
        "# RELEASE M6\n\n## 一、tag 前事实\n\n- x\n\n## 三、覆盖对账\n\n"
        "| 出口门 | 状态 | 证据 |\n| --- | --- | --- |\n"
        "| a | 实现 | x |\n| b | 不适用 | y |\n| c | 待首推 | z |\n",
    )


def m_layout_release_valid(m):
    """阴性对照：完整留档（两栏 + 覆盖对账 + 3 条三态行）必须放行。"""
    for rel in (PLAN00, PLAN05, README):
        text = m.read(rel)
        lines = []
        for line in text.splitlines(True):
            stripped = line.lstrip()
            if stripped.startswith("|") and "M6" in line and "⬜" in line:
                line = line.replace("⬜", "✅", 1)
            lines.append(line)
        m.write(rel, "".join(lines))
    _write_complete_handoff(m, 6)
    m.write_new(
        "plan/RELEASE-M6.md",
        "# RELEASE M6\n\n## 一、tag 前事实\n\n- x\n\n## 二、tag 后追加\n\n- y\n\n"
        "## 三、覆盖对账\n\n| 出口门 | 状态 | 证据 |\n| --- | --- | --- |\n"
        "| a | 实现 | x |\n| b | 不适用 | y |\n| c | 待首推 | z |\n",
    )


def m_layout_doc_tools_missing(m):
    m.append(PLAN05, "\n| 新门 | `tools/check_nonexistent.py` |\n")


def m_layout_doc_tools_stale(m):
    """往 PENDING_TOOLS 塞一条"所属里程碑已 ✅"的过期登记 → 必须红。"""
    m.replace(
        "tools/check_sprint_layout.py",
        '"tools/gen_fixtures.py": 3,',
        '"tools/gen_fixtures.py": 3,\n    "tools/check_nonexistent.py": 0,',
    )
    m.append(PLAN05, "\n| 新门 | `tools/check_nonexistent.py` |\n")


def m_desens_drive(m):
    m.write_new("plan/NOTES-tmp.md", "临时路径 D:\\work\\repo\\src\n")


def m_desens_msys(m):
    m.write_new("plan/NOTES-tmp.md", "临时路径 /d/Users/someone/project/src\n")


def m_desens_username(m):
    m.write_new("plan/NOTES-tmp.md", "路径 C:/Users/someone/project\n")


def m_desens_loopback(m):
    m.write_new("plan/NOTES-tmp.md", "代理 127.0.0.1:7897\n")


def m_desens_placeholder(m):
    """阴性对照：占位符形态必须放行。"""
    m.write_new("plan/NOTES-tmp.md", "占位 C:\\Users\\<user>\\repo 与 <local-proxy>\n")


def m_threshold_bare(m):
    m.append(
        "src/bpreflight/severity.py",
        "\n\ndef _leaked_threshold():\n    return 5.88\n",
    )


def m_threshold_struct_ok(m):
    """阴性对照：结构性常量（0/1/2/16/0.05）必须放行。"""
    m.append(
        "src/bpreflight/severity.py",
        "\n\ndef _structural():\n    return (0, 1, 2, 16, 0.05)\n",
    )


def m_floor_match(m):
    m.append(
        "src/bpreflight/paths.py",
        "\n\ndef _peek(value):\n    match value:\n        case 1:\n            return 1\n    return 0\n",
    )


def m_floor_builtin_generic(m):
    m.append(
        "src/bpreflight/paths.py",
        "\n\ndef _sizes(items: list[int]) -> dict[str, int]:\n    return {}\n",
    )


def m_floor_none(m):
    """阴性对照：合法的 3.8 语法不得误红。"""
    m.append(
        "src/bpreflight/paths.py",
        "\n\ndef _fine(a, b=2):\n    items = [x for x in (a, b)]\n    return {k: v for k, v in enumerate(items)}\n",
    )


MUTATIONS = [
    # (label, gate, mutate, expect_red)
    ("L1 删 AGENTS.md", "layout", m_layout_files, True),
    ("L2 删 plan/00 装订行", "layout", m_layout_binding, True),
    ("L3 删一份必需小节", "layout", m_layout_sections, True),
    ("L4 只在一个副本翻状态（两态探测）", "layout", m_layout_status, True),
    ("L5 标 M1 ✅ 但不写 HANDOFF-M1", "layout", m_layout_handoffs, True),
    ("L6 缺口格提已 ✅ 的 M0", "layout", m_layout_gaps, True),
    ("L7 缺口格点名文件名（阴性对照，必须绿）", "layout", m_layout_gaps_file_ref, False),
    ("L8 台账行挂未完成", "layout", m_layout_ledger, True),
    ("L9 M6 ✅ 但缺发布留档（激活分支）", "layout", m_layout_release_activation, True),
    ("L10 留档缺 tag 后追加 栏", "layout", m_layout_release_two_columns, True),
    ("L11 留档完整（阴性对照，必须绿）", "layout", m_layout_release_valid, False),
    ("L12 文档点名不存在的脚本", "layout", m_layout_doc_tools_missing, True),
    ("L13 过期 PENDING_TOOLS 登记", "layout", m_layout_doc_tools_stale, True),
    ("D1 盘符绝对路径", "desens", m_desens_drive, True),
    ("D2 MSYS 用户路径", "desens", m_desens_msys, True),
    ("D3 本机用户名", "desens", m_desens_username, True),
    ("D4 回环代理端口", "desens", m_desens_loopback, True),
    ("D5 占位符形态（阴性对照，必须绿）", "desens", m_desens_placeholder, False),
    ("T1 src 里写裸阈值", "thresholds", m_threshold_bare, True),
    ("T2 结构性常量（阴性对照，必须绿）", "thresholds", m_threshold_struct_ok, False),
    ("P1 3.10 的 match", "floor", m_floor_match, True),
    ("P2 3.9 的内建泛型注解", "floor", m_floor_builtin_generic, True),
    ("P3 合法 3.8 语法（阴性对照，必须绿）", "floor", m_floor_none, False),
]


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #


def baseline(root):
    """基线：四道门必须全绿，且每条都报出"扫到了几个"（非空跑自证）。"""
    problems = []
    for gate in ("layout", "desens", "thresholds", "floor"):
        code, output = run_gate(root, gate)
        if code != 0:
            problems.append("基线 {} 门应为绿，实际 rc={}\n{}".format(gate, code, output))
        if "扫描" not in output and "扫到" not in output:
            problems.append("基线 {} 门没有报出扫描数量（空跑自证缺失）".format(gate))
    return problems


def main():
    problems = []
    passed = []
    with tempfile.TemporaryDirectory(prefix="bpf-gates-") as tmp:
        base = os.path.join(tmp, "repo")
        shutil.copytree(ROOT, base, ignore=IGNORE)

        problems.extend(baseline(base))

        for label, gate, mutate, expect_red in MUTATIONS:
            work = os.path.join(tmp, "m")
            if os.path.isdir(work):
                shutil.rmtree(work)
            shutil.copytree(base, work, ignore=IGNORE)
            mutator = Mutator(work)
            try:
                mutate(mutator)
            except AssertionError as exc:
                problems.append("{}：变异靶子无效（{}）".format(label, exc))
                continue
            code, output = run_gate(work, gate)
            is_red = code != 0
            if is_red == expect_red:
                passed.append(label)
            else:
                problems.append(
                    "{}：期望{}，实际{}（{} 门 rc={}）\n{}".format(
                        label,
                        "红" if expect_red else "绿",
                        "红" if is_red else "绿",
                        gate,
                        code,
                        output.strip(),
                    )
                )

    out = io.StringIO()
    out.write("门自检（变异验证） · 每组变异都在临时副本上做，工作树不动\n")
    out.write("=" * 60 + "\n")
    for label in passed:
        out.write("OK    {}\n".format(label))
    for problem in problems:
        out.write("FAIL  {}\n".format(problem))
    out.write("=" * 60 + "\n")
    out.write(
        "共 {} 组变异：符合预期 {} / 不符合 {}（其中阴性对照 {} 组）\n".format(
            len(MUTATIONS),
            len(passed),
            len(problems),
            sum(1 for item in MUTATIONS if not item[3]),
        )
    )
    out.write("结论: {}\n".format("全绿" if not problems else "FAIL"))
    sys.stdout.write(out.getvalue())
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
