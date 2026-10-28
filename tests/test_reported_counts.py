# -*- coding: utf-8 -*-
"""自指守门：文档里自称的测试条数必须等于**真实收集条数**。

为什么这条测试存在（D1）：本仓的"数字 + passed"已经漂了四代
（253 → 269 → 299 → 303），每一代都是"做完没回填"而不是笔误；而且错值
随 sdist 发布了出去，与同一份 sdist 里 `plan/RELEASE-M6.md` 的 303 自相矛盾。
全仓此前**没有任何断言**守着这个数字——只靠人记得改。

口径（三条）：

  1. `test_documented_counts_match_collected`
     `subprocess` 跑一次真实收集，解析出条数；再断言文档里每个
     「数字 + passed」/「数字 + tests」都等于它。
  2. `test_no_stale_299_string`
     当前事实文档里不得出现 "299 passed"（D1 的具体错值；留一条针对性断言，
     避免以后有人只改一半就以为好了）。
  3. `test_count_gate_finds_the_docs`
     阴性对照：把两个目标文档读成不存在时，前两条**必须**失败——
     证明它们是"真的在判文档"，而不是在空集合上永远绿。

**判据只认"当前事实"文档**：`plan/05-里程碑与发布.md`（里程碑状态表 + DoD +
已知未验证项）与 `plan/HANDOFF-M6.md`（第 6 棒交接单）。历史交接单
（`HANDOFF-M3/M4/M5`）里写的 253/269 是**那一棒当时的真值**，不是当前事实，
改动它等于篡改历史记录，因此不在判据内（`plan/06` 的 R6 行同理，它记的是
"M4 已补跑"这个历史事件）。

本模块自身不跑被测测试：子进程只做 `--collect-only`。
"""

import io
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: "当前事实"文档 —— 它们的测试数字必须是**此刻**的真值。
FACT_DOCS = (
    "plan/05-里程碑与发布.md",
    "plan/HANDOFF-M6.md",
    "README.md",
)

#: 「数字 + passed」/「数字 + tests」/「数字 + 条测试」三种自称形态。
COUNT_RE = re.compile(r"(\d+)\s*(passed|tests)\b")

#: 收集行形如 `303 tests collected in 0.11s` / `303 tests collected`。
COLLECTED_RE = re.compile(r"^(\d+)\s+tests?\s+collected", re.M)


def _read(rel):
    path = REPO_ROOT / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _collected_count():
    """真实收集条数（子进程只 collect，不执行任何测试）。

    `-p no:cacheprovider` 避免子进程写 `.pytest_cache` 干扰工作树；
    `--collect-only -q` 的汇总行是所有 pytest 版本都有的稳定形态。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    text = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, "收集失败（rc={}）：\n{}".format(proc.returncode, text[-2000:])
    matches = COLLECTED_RE.findall(text)
    assert matches, "收集输出里找不到 'N tests collected' 汇总行：\n{}".format(text[-2000:])
    return int(matches[-1])


def _declared_counts(text):
    """文档里所有「数字 + passed/tests」的 (数字, 原文片段) 列表。"""
    return [(int(m.group(1)), m.group(0)) for m in COUNT_RE.finditer(text)]


def _scan(docs):
    """返回 (真实条数, 违规列表)。docs 里读不到的会被记成违规（不静默跳过）。"""
    real = _collected_count()
    problems = []
    scanned = 0
    for rel in docs:
        text = _read(rel)
        if text is None:
            problems.append("{}: 读不到（判据不能静默跳过）".format(rel))
            continue
        scanned += 1
        for number, snippet in _declared_counts(text):
            if number != real:
                problems.append("{}: 写 {!r}，真实收集 {} 条".format(rel, snippet, real))
    return real, problems, scanned


def test_documented_counts_match_collected():
    """文档里每个「数字 + passed/tests」都等于真实收集条数。"""
    real, problems, scanned = _scan(FACT_DOCS)
    assert scanned > 0, "0 份文档被读到 —— 判据空跑"
    assert not problems, (
        "自述测试数与实际收集条数（{}）不一致：\n  {}".format(real, "\n  ".join(problems))
    )


def test_no_stale_299_string():
    """当前事实文档里不得出现 "299 passed"（D1 的具体错值）。"""
    found = []
    for rel in ("plan/05-里程碑与发布.md", "plan/HANDOFF-M6.md"):
        text = _read(rel)
        assert text is not None, "{}: 读不到 —— 阴性对照失去靶子".format(rel)
        if "299 passed" in text:
            found.append(rel)
    assert not found, "这些文档仍写 '299 passed'（实测 303）：{}".format(", ".join(found))


def test_count_gate_finds_the_docs():
    """阴性对照：两个目标文档读不到时，前两条必须失败。

    "读不到就当通过"是最常见的假门形态（断言落在空集合上恒真）。
    这里直接喂不存在的路径，断言 `_scan` 把"读不到"记成违规。
    """
    missing = ("plan/DOES-NOT-EXIST-A.md", "plan/DOES-NOT-EXIST-B.md")
    _real, problems, scanned = _scan(missing)
    assert scanned == 0, "不存在的文档不该被算进扫描面（实际 {}）".format(scanned)
    assert len(problems) == len(missing), (
        "阴性对照失效：两个不存在的文档应当产生 2 条违规，实际 {} 条：{}".format(
            len(problems), problems
        )
    )
    for rel in missing:
        assert any(rel in problem for problem in problems), (
            "阴性对照失效：没有针对 {} 的违规记录".format(rel)
        )
