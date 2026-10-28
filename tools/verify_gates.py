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
    "ci": "tools/check_ci_workflow.py",
    # `gen_fixtures.py --check` 是 M3 的第七道常规检查：它判"fixture 清单与判定行为
    # 是否还一致"。放进这里是因为它的失败模式与门完全相同（该红时必须红）。
    "fixtures": "tools/gen_fixtures.py --check",
}

CI_WORKFLOW = ".github/workflows/ci.yml"

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
    parts = GATES[gate].split()
    script = os.path.join(root, parts[0])
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [PY, "-X", "utf8", script] + parts[1:],
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


def _milestones_with(root, marker):
    """plan/05 状态表里带某个状态记号的里程碑号（按出现序）。

    **只认首格就是 `M<k>` 的行**（与布局门的 `STATUS_LINE` 同口径）：`plan/05` §四
    "已知未验证项"里有一行尾部写着 `M6`、状态格是 `⬜`——按"行里含 `M<k>`"取会把
    **表尾引用**误当成状态行（M6 收尾实测：L4/L5 因此失去了靶子，变异静默变绿）。
    """
    found = []
    for line in m_read(root, PLAN05).splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("|") or marker not in stripped:
            continue
        cells = [c.strip().strip("*") for c in stripped.strip().strip("|").split("|")]
        if not cells:
            continue
        token = cells[0]
        if token.startswith("M") and token[1:].isdigit():
            found.append(int(token[1:]))
    return found


def _pending_milestones(root):
    """plan/05 状态表里当前仍是 ⬜ 的里程碑号（按出现序）。"""
    return _milestones_with(root, "⬜")


def m_read(root, rel):
    with io.open(os.path.join(root, rel), "r", encoding="utf-8") as handle:
        return handle.read()


def m_layout_status(m):
    """两态探测：让**一个副本**与另外两个不一致（只翻一个副本 → 必须红）。

    靶子由当前进度算出，不写死里程碑号：还有 ⬜ 里程碑时把它只在一个副本里翻 ✅；
    **全都 ✅ 之后**（发布收尾）改成把最后一个已 ✅ 的里程碑**只在 plan/05 退回 ⬜**。
    判据始终是"副本之间不一致"，不依赖"项目还没做完"这个瞬态
    （`references/methodology-binding.md` 假门族 ⑭「靶子过期」）。
    """
    pending = _pending_milestones(m.root)
    if pending:
        m.set_status([PLAN05], pending[0], "⬜", "✅")
        return
    done = _milestones_with(m.root, "✅")
    assert done, "plan/05 里既没有 ⬜ 也没有 ✅ 里程碑 —— 这条变异失去了靶子"
    m.set_status([PLAN05], done[-1], "✅", "⬜")


def m_layout_handoffs(m):
    """标一个里程碑 ✅，但让它的**交接单不存在** → 必须要求 HANDOFF 而它不在。

    靶子由构造算出，不写死里程碑号（写死 M1 会在 M1 的交接单落盘后失效，
    `references/methodology-binding.md` 假门族 ⑭「靶子过期」）。

    两态探测（M5 收尾补，M6 收尾再补）：下一棒的交接单通常在上一棒收尾时就**预写**了
    （`plan/HANDOFF-M<k+1>.md`），于是"待办里程碑里没有交接单的那个"可能一个都不剩
    ——那时先把该里程碑的交接单删掉；**全部里程碑都 ✅ 之后**（发布收尾）就没有待办项可翻，
    改为"已 ✅ 的末尾里程碑 + 删掉它的交接单"——变异仍是"标 ✅ 却缺交接单"这一件事。
    """
    pending = _pending_milestones(m.root)
    if pending:
        candidates = [
            milestone
            for milestone in pending
            if not os.path.isfile(m.path("plan/HANDOFF-M{}.md".format(milestone)))
        ]
        milestone = candidates[0] if candidates else pending[0]
    else:
        done = _milestones_with(m.root, "✅")
        assert done, "plan/05 里既没有 ⬜ 也没有 ✅ 里程碑 —— 这条变异失去了靶子"
        milestone = done[-1]
    # `milestone` 由构造保证是"要么待办、要么已收尾"的里程碑；下面删掉的一定是它的交接单。
    prewritten = "plan/HANDOFF-M{}.md".format(milestone)
    removed = os.path.isfile(m.path(prewritten))
    if removed:
        m.delete(prewritten)

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
    assert removed or changed > 0, "M{} 既没删到交接单、也没翻到状态行".format(milestone)


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
    """激活即证伪：M6 在三处副本标 ✅，而发布留档不存在 → LAYOUT.RELEASE 必须红。

    **两态探测（M6 收尾补）**：发布留档存在之后，"M6 还是 ⬜"这个前提就没有了。
    此时改为**删掉留档**（M6 仍 ✅）——判据仍是"✅ 却缺留档"这一件事，
    不随"项目做到哪一步"而失效（假门族 ⑭「靶子过期」）。
    """
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
    if os.path.isfile(m.path("plan/RELEASE-M6.md")):
        m.delete("plan/RELEASE-M6.md")


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
    """往 PENDING_TOOLS 塞一条"所属里程碑已 ✅"的过期登记 → 必须红。

    靶子是 `PENDING_TOOLS = {}` 这个空表：M3 落地后表已清空（正确终态），
    所以这里从空表出发注入一条过期登记。断言替换真的产生字节变化，
    避免"表里本来就有那一行"让变异退化成 no-op。
    """
    m.replace(
        "tools/check_sprint_layout.py",
        "PENDING_TOOLS = {}",
        'PENDING_TOOLS = {\n    "tools/check_nonexistent.py": 0,\n}',
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


def m_desens_handoff_dir(m):
    """阴性对照：`update/`（二次迭代交接目录）里写盘符路径必须**放行**。

    这条与 D1 是一对：D1 证明"真入库的目录里写盘符会红"，本组证明
    "被收编的本地交接目录里写同样的东西不会红"。两条一起才说明收编是**定向的**
    （缩到零判定面的假收编会让 D1 也变绿，而 D1 仍红）。

    D5 之前 `update/` 不在 `SKIP_DIRS`：做一次正经诊断就把脱敏门打红（126 份扫到、
    命中 1 处）。收编后它进 `SKIP_DIRS`（与 `.gitignore` 成对）。
    """
    m.write_new("update/NOTES-tmp.md", "临时路径 D:\\work\\repo\\src\n")


def m_threshold_bare(m):
    m.append(
        "src/bpreflight/severity.py",
        "\n\ndef _leaked_threshold():\n    return 5.88\n",
    )


def m_threshold_bare_in_m3(m):
    """M3 的检查模块同样在扫描面内：在 `print/` 里写裸阈值也必须红。

    M3 新增了 7 个判定模块，最小的那种退化就是"顺手在 color.py 里写 0.30"——
    这条变异证明 `print/` 确实被门扫到了，而不是门沿用了旧的文件清单。
    """
    m.append(
        "src/bpreflight/print/color.py",
        "\n\ndef _leaked_threshold():\n    return 0.30\n",
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


def m_floor_tools_builtin_generic(m):
    """`tools/` 里写内建泛型注解 → 必须红（D2：扫描面曾漏掉整个 `tools/`）。

    实测背景：`SCAN_ROOTS` 只有 `src/bpreflight` 与 `tests` 时，往 `tools/` 放一个
    `list[int]` 注解该门仍 `PASS 扫描 52 份` exit 0，而低版本解释器跑该文件是
    `TypeError: 'type' object is not subscriptable` —— 那就是"没有门的门"。
    """
    m.write_new(
        "tools/_probe39.py",
        "def _sizes(items: list[int]) -> dict[str, int]:\n    return {}\n",
    )


def m_floor_none(m):
    """阴性对照：合法的 3.8 语法不得误红。"""
    m.append(
        "src/bpreflight/paths.py",
        "\n\ndef _fine(a, b=2):\n    items = [x for x in (a, b)]\n    return {k: v for k, v in enumerate(items)}\n",
    )


def m_floor_tools_none(m):
    """阴性对照：`tools/` 里写普通合法代码不得误红（新判定面不许过度报警）。"""
    m.write_new(
        "tools/_probe_ok.py",
        "def _fine(a, b=2):\n    return {k: v for k, v in enumerate((a, b))}\n",
    )


def m_ci_unquoted_colon(m):
    """M0 真实踩过的那一脚：未加引号的 step 名里出现 `": "` → 该 YAML 不可解析。"""
    m.replace(
        CI_WORKFLOW,
        '- name: "Smoke (installed CLI: help + example run)"',
        "- name: Smoke (installed CLI: help + example run)",
    )


def m_ci_missing_gate_step(m):
    """删掉一条门的独立 step（决策 D18）→ 必须红。"""
    m.replace(
        CI_WORKFLOW,
        '      - name: "CI workflow gate (workflow YAML must stay in a parseable subset)"\n'
        "        run: python tools/check_ci_workflow.py\n",
        "",
    )


def m_ci_two_gates_one_step(m):
    """把两个门塞进同一个 step → 必须红（D18 的"独立 step"判据）。"""
    m.replace(
        CI_WORKFLOW,
        '      - name: "CI workflow gate (workflow YAML must stay in a parseable subset)"\n'
        "        run: python tools/check_ci_workflow.py\n",
        '      - name: "Two gates in one step"\n'
        "        run: |\n"
        "          python tools/check_ci_workflow.py\n"
        "          python tools/check_python_floor.py\n",
    )


def m_ci_matrix_drop_floor(m):
    """矩阵里把所有下限版本的腿都删掉 → 必须红（`requires-python` 的下限要有实跑）。

    M6.1 下限从 3.8 抬到 3.12 后，靶子跟着变：判据从"必须含 3.8 与 3.12"改为
    "必须含 `pyproject.toml` 里的下限"。因此变异改成把**两条** 3.12 腿都换掉——
    只换一条（ubuntu）仍会被 windows 那条满足，变异就退化成 no-op。
    """
    text = m.read(CI_WORKFLOW)
    assert text.count('python: "3.12"') >= 1, "矩阵里没有 3.12 腿 —— 变异靶子失效"
    m.write(CI_WORKFLOW, text.replace('python: "3.12"', 'python: "3.11"'))


def m_ci_negative_control(m):
    """阴性对照：合法形状（引号包裹 / 块标量 / 列表 / 注释）必须放行。"""
    m.append(
        CI_WORKFLOW,
        '\n  demo:\n'
        '    runs-on: ubuntu-latest\n'
        '    steps:\n'
        '      - name: "Colon in a quoted name: like this"\n'
        "        run: |\n"
        "          echo ok  # trailing comment is fine\n"
        "      - name: list shaped\n"
        "        with:\n"
        "          args: [a, b]\n",
    )


def m_fixtures_drift(m):
    """篡改清单里的期望 → `--check` 必须红（判定行为变了却没人重生成清单）。"""
    text = m.read("fixtures/manifest.json")
    assert '"verdict": "pass"' in text, "清单里没有 pass 期望 —— 变异靶子失效"
    m.replace(
        "fixtures/manifest.json",
        '"verdict": "pass"',
        '"verdict": "fail"',
    )


def m_fixtures_thresholds_identity(m):
    """篡改阈值册身份 → 必须红（数据改了但清单没同提交重生成）。"""
    text = m.read("fixtures/manifest.json")
    marker = '"thresholds_sha256": "'
    assert marker in text, "清单里没有 thresholds_sha256"
    start = text.index(marker) + len(marker)
    digest = text[start:start + 64]
    assert len(digest) == 64, digest
    m.replace("fixtures/manifest.json", '"thresholds_sha256": "{}"'.format(digest),
              '"thresholds_sha256": "{}"'.format("0" * 64))


def m_fixtures_negative_control(m):
    """阴性对照：清单不动，`--check` 必须绿。"""
    # 只碰一个与本门无关的文件，证明"没变异"时门确实是绿的。
    m.append("plan/06-交付对标与决策.md", "\n")


MUTATIONS = [
    # (label, gate, mutate, expect_red)
    ("L1 删 AGENTS.md", "layout", m_layout_files, True),
    ("L2 删 plan/00 装订行", "layout", m_layout_binding, True),
    ("L3 删一份必需小节", "layout", m_layout_sections, True),
    ("L4 只在一个副本翻状态（两态探测）", "layout", m_layout_status, True),
    ("L5 标一个里程碑 ✅ 但缺它的交接单", "layout", m_layout_handoffs, True),
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
    ("D6 本地交接目录 update/ 不在扫描面（阴性对照，必须绿）", "desens", m_desens_handoff_dir, False),
    ("T1 src 里写裸阈值", "thresholds", m_threshold_bare, True),
    ("T2 结构性常量（阴性对照，必须绿）", "thresholds", m_threshold_struct_ok, False),
    ("T3 M3 的 print/ 里写裸阈值", "thresholds", m_threshold_bare_in_m3, True),
    ("P1 3.10 的 match", "floor", m_floor_match, True),
    ("P2 3.9 的内建泛型注解", "floor", m_floor_builtin_generic, True),
    ("P3 合法语法（阴性对照，必须绿）", "floor", m_floor_none, False),
    ("P4 tools/ 里写内建泛型注解", "floor", m_floor_tools_builtin_generic, True),
    ("P5 tools/ 里写普通合法代码（阴性对照，必须绿）", "floor", m_floor_tools_none, False),
    ("C1 未加引号的 step 名里带 ':'（M0 真实踩过）", "ci", m_ci_unquoted_colon, True),
    ("C2 删掉一条门的独立 step", "ci", m_ci_missing_gate_step, True),
    ("C3 两个门塞进同一个 step", "ci", m_ci_two_gates_one_step, True),
    ("C4 矩阵里删掉下限（3.12 腿全换掉）", "ci", m_ci_matrix_drop_floor, True),
    ("C5 合法形状（阴性对照，必须绿）", "ci", m_ci_negative_control, False),
    ("F1 清单期望漂移", "fixtures", m_fixtures_drift, True),
    ("F2 阈值册身份过期", "fixtures", m_fixtures_thresholds_identity, True),
    ("F3 清单未动（阴性对照，必须绿）", "fixtures", m_fixtures_negative_control, False),
]


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #


def baseline(root):
    """基线：全部门必须全绿，且每条都报出"扫到了几个"（非空跑自证）。"""
    problems = []
    for gate in sorted(GATES):
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
