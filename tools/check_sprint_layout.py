#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""布局门（方法论装订第②件）：把"项目还长在方法论上"变成可跑红的断言。

判据一律落**仓库内文件**，不读 git 元数据（浅克隆下 `git tag` / 历史深度会翻转）。

判据清单（每加一条都要在 `tools/verify_gates.py` 里配一组变异）：

  LAYOUT.FILES        必备文件齐备
  LAYOUT.BINDING_HEAD plan/00 顶部装订行（三锚点同现，顺序无关）
  LAYOUT.SECTIONS     各计划文档的必需小节
  LAYOUT.STATUS       里程碑状态在**全部**副本间一致；逐副本命中行数可见；合计 0 行 = 空跑
  LAYOUT.HANDOFFS     每个 ✅ 里程碑一份交接单且七节齐
  LAYOUT.GAPS         plan/06 缺口列不得再提已 ✅ 的里程碑（按表头定位列、剥文件名）
  LAYOUT.LEDGER       承诺-证据台账（第四份状态副本）不得挂未完成标记
  LAYOUT.RELEASE      发布里程碑 ✅ 后必须有发布留档（两栏 + 覆盖对账）
  LAYOUT.DOC_TOOLS    文档点名的 tools/ 脚本必须有实物（未到里程碑的登记为 PENDING）

设计纪律（来自 `references/methodology-binding.md` 的 19 条假门族）：
  ① 真值不取自任何单一副本 —— 逐副本采集，任一不一致即红；
  ② 按表头定位列号，不靠"行里含某词"；
  ③ 多锚点用"同现"而不是"或"；
  ④ 判据顺序无关；
  ⑤ 状态只认表格行，散文状态行不参与判定；
  ⑥⑧ 匹配前剥掉行内代码与文件名（状态引用才该被判，文件引用应放行）；
  ⑦⑩ 缺口表扫描面 = 表头 → 首条非表格行即止，并把行数打进结论；
  ⑪ 每份副本单独记命中行数，0 行可见，合计 0 行即 FAIL；
  ⑫⑬ PENDING_TOOLS 三个状态，且登记表清空是应当被断言的终态；
  ⑮ 门只证"副本互相同意"，不证"与事实一致" —— 收尾棒另有"时效扫描"规定动作。

退出码：0 全绿 / 1 有 FAIL。
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHECKS = []
SCANNED = {"docs": 0, "handoffs": 0, "copies": 0, "doc_tools": 0, "handoff_files": 0}


def add(check_id, ok, detail):
    CHECKS.append({"id": check_id, "ok": ok, "detail": detail})


def read(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        return None
    with io.open(path, "r", encoding="utf-8") as handle:
        return handle.read()


REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "data/README.md",
    "plan/00-README总览.md",
    "plan/01-题目文档.md",
    "plan/02-架构与技术选型.md",
    "plan/03-模块详设.md",
    "plan/04-数据计划.md",
    "plan/05-里程碑与发布.md",
    "plan/06-交付对标与决策.md",
]

#: 三锚点**同现于一行**：方法论名 + 布局门命令 + 装订日期。顺序无关（假门族 ③④）。
BINDING_LINE = re.compile(
    r"^>(?=.*ai-tool-project-sprint)(?=.*check_sprint_layout)(?=.*20\d{2}-\d{2}-\d{2}).*$",
    re.M,
)

REQUIRED_SECTIONS = {
    "plan/00-README总览.md": ["文档索引", "决策记录", "承诺-证据台账", "里程碑"],
    "plan/01-题目文档.md": ["任务要求", "评分标准", "边界与非目标"],
    "plan/02-架构与技术选型.md": ["分层", "构建"],
    "plan/03-模块详设.md": ["通用契约", "CLI 契约"],
    "plan/04-数据计划.md": ["数据清单", "真值纪律"],
    "plan/05-里程碑与发布.md": ["DoD", "已知未验证项"],
    "plan/06-交付对标与决策.md": ["评分对标", "风险登记", "缺口"],
    "data/README.md": ["依据查证", "数值口径"],
}

#: 项目**已声明**的豁免（写在 AGENTS.md 里）：M0 的收尾记录就是计划套件本身。
EXEMPT_MILESTONES = (0,)

#: HANDOFF 七节（超集合法：只断言"必需节都存在"）。
HANDOFF_SECTIONS = [
    "当前进度",
    "当前事实",
    "待办",
    "既定口径",
    "环境坑",
    "DoD",
    "命令速查",
]

#: 状态副本：同一里程碑在这几处的状态必须互相一致。**逐处采集，不取任何单一副本为真值。**
STATUS_COPIES = [
    "plan/00-README总览.md",
    "plan/05-里程碑与发布.md",
    "README.md",
]

#: 只认"状态行"：表格行且首格就是里程碑号（散文状态行不参与，假门族 ⑤⑮）。
STATUS_LINE = re.compile(r"^\|\s*\*{0,2}M(\d+)\b")
PENDING_MARKERS = ("⬜", "🟡", "未开始", "未执行", "待执行", "待确认", "未开工")
DONE_MARKERS = ("✅",)

#: 一行要成为"状态行"，必须真的带一个状态记号。
#: 否则"里程碑总览表"（首格是 M<k>、但没有状态列）会被误读成 done——这是 ⑮ 的同族假红。
STATUS_TOKENS = DONE_MARKERS + PENDING_MARKERS

#: 发布里程碑（`plan/05` 状态表里出现过的最大里程碑号）。未 ✅ 时 LAYOUT.RELEASE 报"不适用"。
RELEASE_MILESTONE = 6

#: 文档已点名、但**尚未到**该里程碑的脚本。里程碑翻 ✅ 后必须删除，否则 stale 分支变红。
#: M3 落地后 `tools/gen_fixtures.py` 已在位，本表清空——空表是正确终态（假门族 ⑬）。
PENDING_TOOLS = {}
#: 确实不打算实现的脚本（逐条写理由）。当前为空表 —— 空表本身是正确终态（假门族 ⑬）。
EXEMPT_TOOLS = {}

DOC_GLOBS = ["AGENTS.md", "README.md"]
TOOL_PATH_RE = re.compile(r"tools/[\w.-]+\.(?:py|mjs|js|sh|ps1)")


# --------------------------------------------------------------------------- #
# 判据
# --------------------------------------------------------------------------- #


def check_required_files():
    missing = [rel for rel in REQUIRED_FILES if not os.path.isfile(os.path.join(ROOT, rel))]
    SCANNED["docs"] = len(REQUIRED_FILES) - len(missing)
    add(
        "LAYOUT.FILES",
        not missing,
        "缺: " + ",".join(missing) if missing else "{} 份齐备".format(SCANNED["docs"]),
    )


def check_binding_head():
    text = read("plan/00-README总览.md") or ""
    ok = bool(BINDING_LINE.search(text))
    add(
        "LAYOUT.BINDING_HEAD",
        ok,
        "plan/00 顶部有装订行（三锚点齐）"
        if ok
        else "plan/00 顶部缺装订行（需同现：方法论名 + 布局门命令 + 装订日期）",
    )


def check_sections():
    """必需小节必须出现在**标题行**里。

    不能写成"关键词 in 全文"：那样引言里提到一句就能满足判据，缺节变异恒绿
    （`references/methodology-binding.md` Python 重写数据点③）。
    """
    bad = []
    scanned = 0
    for rel, needles in sorted(REQUIRED_SECTIONS.items()):
        text = read(rel)
        if text is None:
            continue
        scanned += 1
        headings = [
            line for line in text.splitlines() if re.match(r"^#{1,4}[^\n]*", line)
        ]
        missing = [
            n for n in needles if not any(n in heading for heading in headings)
        ]
        if missing:
            bad.append("{}: {}".format(rel, "/".join(missing)))
    if scanned == 0:
        add("LAYOUT.SECTIONS", False, "0 份文档被读到 —— 判据空跑")
        return
    add(
        "LAYOUT.SECTIONS",
        not bad,
        "；".join(bad) if bad else "{} 份文档小节齐备（逐节锚到标题行）".format(scanned),
    )


def collect_states():
    """逐副本采集 -> (Map<k, Set<state>>, Map<copy, rows>)。"""
    states = {}
    rows_by_copy = {}
    for rel in STATUS_COPIES:
        text = read(rel)
        if text is None:
            continue
        SCANNED["copies"] += 1
        rows = 0
        for line in text.splitlines():
            match = STATUS_LINE.match(line)
            if not match:
                continue
            if not any(token in line for token in STATUS_TOKENS):
                continue  # 总览表里没有状态列的行，不算状态行
            rows += 1
            pending = any(marker in line for marker in PENDING_MARKERS)
            state = "pending" if pending else "done"
            states.setdefault(int(match.group(1)), set()).add(state)
        rows_by_copy[rel] = rows
    return states, rows_by_copy


def check_status_agreement(states, rows_by_copy):
    conflicts = [
        "M{} 在副本间状态不一致（{}）".format(k, " vs ".join(sorted(v)))
        for k, v in sorted(states.items())
        if len(v) > 1
    ]
    total = sum(rows_by_copy.values())
    per_copy = " ".join(
        "{}:{}".format(os.path.basename(rel), rows) for rel, rows in sorted(rows_by_copy.items())
    )
    if total == 0:
        add(
            "LAYOUT.STATUS",
            False,
            "所有副本合计 0 行状态行（判据空跑）：{}".format(per_copy or "(no copies read)"),
        )
        return
    add(
        "LAYOUT.STATUS",
        not conflicts,
        "；".join(conflicts)
        if conflicts
        else "{} 处副本 × {} 个里程碑 状态全一致（行数 {}）".format(
            SCANNED["copies"], len(states), per_copy
        ),
    )


def check_handoffs(done, all_milestones):
    last = max(all_milestones) if all_milestones else 0
    # 盘上实际有几份交接单（含"下一棒已预写、对应里程碑还没 ✅"的那种）：
    # 与"已 ✅ 里程碑各有一份"分开计数，否则 0 会被误读成"没有交接单文件"。
    plan_dir = os.path.join(ROOT, "plan")
    if os.path.isdir(plan_dir):
        SCANNED["handoff_files"] = len(
            [n for n in os.listdir(plan_dir) if n.startswith("HANDOFF-M") and n.endswith(".md")]
        )
    problems = []
    for k in sorted(done):
        if k in EXEMPT_MILESTONES:
            continue
        rel = "plan/HANDOFF-M{}.md".format(k)
        text = read(rel)
        if text is None:
            problems.append("{}（缺{}）".format(rel, "：末棒" if k == last else ""))
            continue
        SCANNED["handoffs"] += 1
        lacking = [n for n in HANDOFF_SECTIONS if n not in text]
        if lacking:
            problems.append("{}（缺节: {}）".format(rel, "/".join(lacking)))
    add(
        "LAYOUT.HANDOFFS",
        not problems,
        "；".join(problems)
        if problems
        else "已 ✅ 里程碑所需交接单 {} 份齐；盘上共 {} 份 HANDOFF（M0 已声明豁免）".format(
            SCANNED["handoffs"], SCANNED["handoff_files"]
        ),
    )


def _strip_refs(cell):
    """剥掉行内代码与文件名（假门族 ⑥⑧）：剩下的才是"状态引用"。"""
    cell = re.sub(r"`[^`]*`", " ", cell)
    cell = re.sub(r"[\w./\\-]+\.(?:md|py|mjs|js|json|toml|txt|whl|gz|zip)", " ", cell)
    return cell


def check_stale_gaps(done):
    text = read("plan/06-交付对标与决策.md") or ""
    lines = text.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if line.startswith("|") and "缺口" in line:
            header_index = index
            break
    if header_index is None:
        add("LAYOUT.GAPS", False, "plan/06 找不到含『缺口』表头的表（判据表搬走了？）")
        return

    headers = [cell.strip() for cell in lines[header_index].strip().strip("|").split("|")]
    try:
        col = headers.index("缺口")
    except ValueError:
        col = 0

    stale = []
    scanned_rows = 0
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        scanned_rows += 1
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        cell = _strip_refs(cells[col] if col < len(cells) else "")
        for k in sorted(done):
            if re.search(r"(^|[^0-9A-Za-z])M{}([^0-9]|$)".format(k), cell):
                stale.append("plan/06 缺口列仍提 M{}: {}".format(k, cell[:60]))
    add(
        "LAYOUT.GAPS",
        not stale,
        "；".join(stale)
        if stale
        else "plan/06 缺口列扫了 {} 行，无已 ✅ 里程碑".format(scanned_rows),
    )


def check_ledger(done):
    text = read("plan/00-README总览.md") or ""
    lines = text.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if line.startswith("|") and "承诺" in line and "状态" in line:
            header_index = index
            break
    if header_index is None:
        add("LAYOUT.LEDGER", False, "plan/00 找不到『承诺-证据台账』表头（承诺项与状态列）")
        return

    SCANNED["copies"] += 1
    bad = []
    rows = 0
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        rows += 1
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        status = cells[-1] if cells else ""
        if not re.search(r"[⬜🟡]|未开始|待 M\d|待开工|未执行", status):
            continue
        for k in sorted(done):
            if re.search(r"(^|[^0-9A-Za-z])M{}([^0-9]|$)".format(k), status):
                bad.append("台账行仍挂未完成: {}".format(status[:60]))
    if rows == 0:
        add("LAYOUT.LEDGER", False, "台账表 0 行 —— 判据空跑")
        return
    add(
        "LAYOUT.LEDGER",
        not bad,
        "；".join(bad) if bad else "台账 {} 行，已 ✅ 里程碑无未完成标记".format(rows),
    )


def check_release_doc(done):
    if RELEASE_MILESTONE not in done:
        add(
            "LAYOUT.RELEASE",
            True,
            "发布里程碑 M{} 未完成，收尾记录尚不适用（已扫 {} 个 ✅ 里程碑）".format(
                RELEASE_MILESTONE, len(done)
            ),
        )
        return
    release = read("plan/RELEASE-M{}.md".format(RELEASE_MILESTONE))
    wrapup = read("plan/WRAPUP-M{}.md".format(RELEASE_MILESTONE))
    if release is None and wrapup is None:
        add(
            "LAYOUT.RELEASE",
            False,
            "缺 plan/RELEASE-M{}.md 或 plan/WRAPUP-M{}.md".format(
                RELEASE_MILESTONE, RELEASE_MILESTONE
            ),
        )
        return
    if release is None:
        add("LAYOUT.RELEASE", True, "WRAPUP 形态")
        return

    two_columns = bool(re.search(r"^##\s*一、.*tag\s*前事实", release, re.M)) and bool(
        re.search(r"^##\s*二、.*tag\s*后追加", release, re.M)
    )
    coverage_heading = bool(re.search(r"^#{2,3}.*覆盖对账", release, re.M))
    three_state_rows = len(
        re.findall(r"^\|.*(?:实现|不适用|待首推).*\|$", release, re.M)
    )
    add(
        "LAYOUT.RELEASE",
        two_columns and coverage_heading and three_state_rows >= 3,
        "两栏:{} 覆盖对账小节:{} 三态行数:{}".format(
            two_columns, coverage_heading, three_state_rows
        ),
    )


def _doc_files():
    files = [rel for rel in DOC_GLOBS if os.path.isfile(os.path.join(ROOT, rel))]
    plan_dir = os.path.join(ROOT, "plan")
    if os.path.isdir(plan_dir):
        files.extend(
            "plan/" + name
            for name in sorted(os.listdir(plan_dir))
            if name.endswith(".md")
        )
    return files


def check_documented_tools(done):
    docs = _doc_files()
    referenced = set()
    for rel in docs:
        text = read(rel)
        if text is None:
            continue
        referenced.update(TOOL_PATH_RE.findall(text))
    if not referenced:
        add(
            "LAYOUT.DOC_TOOLS",
            False,
            "扫了 {} 份文档，0 处 tools/ 引用 —— 判据是空的（阳性对照失败）".format(len(docs)),
        )
        return

    SCANNED["doc_tools"] = len(referenced)
    missing, deferred, stale = [], [], []
    for rel in sorted(referenced):
        exists = os.path.isfile(os.path.join(ROOT, rel))
        if exists:
            continue
        if rel in EXEMPT_TOOLS:
            continue
        milestone = PENDING_TOOLS.get(rel)
        if milestone is None:
            missing.append(rel)
        elif milestone in done:
            stale.append("{}（M{} 已 ✅，登记项必须清理）".format(rel, milestone))
        else:
            deferred.append("{}(M{})".format(rel, milestone))

    problems = missing + stale
    detail = "{} 个文档点名的 tools/ 脚本".format(len(referenced))
    if problems:
        detail += "；问题: " + ",".join(problems)
    elif deferred:
        detail += "；{} 个待里程碑落位: {}".format(len(deferred), ",".join(deferred))
    else:
        detail += " 全部在位"
    add("LAYOUT.DOC_TOOLS", not problems, detail)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def run_all():
    for func in (check_required_files, check_binding_head, check_sections):
        try:
            func()
        except Exception as exc:  # 门永不崩：报一条 FAIL 并继续
            add(getattr(func, "__name__", "check"), False, "{}: {}".format(type(exc).__name__, exc))

    states, rows_by_copy = collect_states()
    done = [k for k, v in states.items() if "done" in v]
    all_milestones = sorted(states)

    guarded = [
        ("LAYOUT.DOC_TOOLS", lambda: check_documented_tools(done)),
        ("LAYOUT.STATUS", lambda: check_status_agreement(states, rows_by_copy)),
        ("LAYOUT.HANDOFFS", lambda: check_handoffs(done, all_milestones)),
        ("LAYOUT.GAPS", lambda: check_stale_gaps(done)),
        ("LAYOUT.LEDGER", lambda: check_ledger(done)),
        ("LAYOUT.RELEASE", lambda: check_release_doc(done)),
    ]
    for label, func in guarded:
        try:
            func()
        except Exception as exc:
            add(label, False, "{}: {}".format(type(exc).__name__, exc))

    return CHECKS


def main():
    checks = run_all()
    failed = [c for c in checks if not c["ok"]]
    out = io.StringIO()
    out.write("布局门（方法论装订） · 判据只落仓库内文件\n")
    out.write("=" * 60 + "\n")
    for check in checks:
        out.write(
            "{}  {}  {}\n".format("PASS" if check["ok"] else "FAIL", check["id"], check["detail"])
        )
    out.write("=" * 60 + "\n")
    out.write(
        "这轮扫到：文档 {} / 交接单 {}（盘上文件 {}）/ 状态副本 {} / 文档点名脚本 {}\n".format(
            SCANNED["docs"],
            SCANNED["handoffs"],
            SCANNED["handoff_files"],
            SCANNED["copies"],
            SCANNED["doc_tools"],
        )
    )
    out.write("结论: {}\n".format("全绿" if not failed else "{} 项 FAIL".format(len(failed))))
    sys.stdout.write(out.getvalue())
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
