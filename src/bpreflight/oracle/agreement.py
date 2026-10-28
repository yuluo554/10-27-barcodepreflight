"""M5 · `agreement` 三态的**纯分类器**（`plan/00` D10、`plan/01` §M5）。

| 状态 | 含义 | 归宿 |
| --- | --- | --- |
| `consistent` | M3 的风险结论与 oracle 回读一致（判有风险解不出 / 判干净解得出来） | 无 |
| `m3_stricter` | M3 判有风险，但 oracle 解得出来 | **known-disagreements**（可能是假阳性） |
| `m3_laxer` | M3 判干净，但 oracle 解不出来 | **bug 通道**：必须修 M3 判定，不许藏进已知差异 |

这条分野是整个 M5 的设计核心（`plan/01` §M5）：**不一致是一等公民**，但"松"和"严"
必须走两条不同的通道——把 `m3_laxer` 藏进"已知差异"等于把 bug 记成免责条款。

`agreement` **不参与** `verdict`（K25）：它是对照，不是第二套判定；`verdict` 只由
findings 派生（`data/README.md` §8.8）。因此本模块只接收**已经算好**的
`m3_verdict`（由编排层从 M3 findings 派生），而不重算任何东西。
"""

from bpreflight import severity as sev

CONSISTENT = "consistent"
M3_STRICTER = "m3_stricter"
M3_LAXER = "m3_laxer"

#: 三值枚举（不新开第四值，也不并入 verdict）。
AGREEMENTS = (CONSISTENT, M3_STRICTER, M3_LAXER)

#: M3 findings 的模块号（`print/common.py` 的 `MODULE`）。
MODULE_M3 = "M3"

#: 触发通路说明，落进报告里（读者不需要回看代码才知道这条差异去了哪）。
_NOTE_STRICTER = (
    "M3 判有风险，oracle 却解得出来 —— 可能是假阳性，记入 known-disagreements（plan/00 D10）"
)
_NOTE_LAXER = (
    "M3 判干净，oracle 解不出来 —— **bug 通道**：必须修 M3 判定，不许记入 known-disagreements"
)


def m3_verdict(findings):
    """M3 findings 自己派生出的 verdict（`pass|warn|fail`），不掺 M1/M2 的结论。"""
    return sev.verdict_for([f.severity for f in findings if f.module == MODULE_M3])


def risky_finding_ids(findings):
    """M3 里真正判了风险的那些 finding id（`warn` / `error`），去重后按字典序。

    同一 id 可能在多侧各报一条（静区的 left/right）。报告要的是"哪条判据起了作用"，
    因此去重；逐条的细节仍在主报告的 findings 里。
    """
    levels = (sev.WARN, sev.ERROR)
    return sorted({f.id for f in findings if f.module == MODULE_M3 and f.severity in levels})


def _entry(agreement, verdict, decoded, finding_ids, note):
    return {
        "agreement": agreement,
        "m3_verdict": verdict,
        "oracle": "decoded" if decoded else "not-decoded",
        "finding_ids": sorted(finding_ids),
        "note": note,
    }


def classify(verdict, decoded, finding_ids=()):
    """Return `(agreement, known_disagreements, bugs)` for one oracle read-back.

    `verdict` is the M3-derived verdict, `decoded` the engine's answer, and
    `finding_ids` the M3 findings that carry risk. The three-way split is total:
    every (verdict, decoded) pair lands in exactly one list.
    """
    risky = verdict in (sev.VERDICT_WARN, sev.VERDICT_FAIL)
    if decoded and risky:
        return (
            M3_STRICTER,
            [_entry(M3_STRICTER, verdict, decoded, finding_ids, _NOTE_STRICTER)],
            [],
        )
    if (not decoded) and not risky:
        return (
            M3_LAXER,
            [],
            [_entry(M3_LAXER, verdict, decoded, finding_ids, _NOTE_LAXER)],
        )
    return CONSISTENT, [], []