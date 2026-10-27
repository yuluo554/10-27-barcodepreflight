"""编排：输入 → 判定 → Report。M0 只做骨架，不产领域判定。

**骨架的诚实态度**（决策 D16）：M0 没有判定层，如果什么都不产，`verdict` 会派生成
`pass`——那是"工具说这个条码没问题"，而它还没做任何判定。因此这里落一条
`implementation_pending`（error），让 M0 的输出**必然 fail**；M1 落地时同提交退役。

`skipped` 是"不可判"的合法通道（`data/README.md` §8.9），**不是** verdict 的第四个值。
"""

import sys

from bpreflight import input as input_mod
from bpreflight import paths
from bpreflight import severity as sev
from bpreflight import thresholds
from bpreflight.report.model import Finding, Report

TOOL_NAME = "bpreflight"

#: M0 骨架的 pending 判定标识。M1 落地后这条必须消失（`tests/test_pipeline_skeleton.py` 守）。
PENDING_ID = "implementation_pending"


def _pending_finding():
    return Finding(
        id=PENDING_ID,
        module="M0",
        severity=sev.ERROR,
        observed="no judgement layer yet",
        target="pipeline",
        threshold=None,
        threshold_status="not-applicable",
        basis="engineering-heuristic",
        evidence={
            "kind": "engineering-heuristic",
            "ref": "src/bpreflight/pipeline.py",
            "quote": "M0 skeleton: M1-M3 judgement not implemented; refusing to report pass",
        },
        fix={
            "kind": "run_supported_milestone",
            "to": "M1",
            "unit": "milestone",
            "rationale": "until M1 lands there is no domain judgement; a pass verdict would be a lie",
        },
        source="skeleton",
    )


def _tools_info(book, deterministic):
    info = {
        "tool": TOOL_NAME,
        "version": _version(),
    }
    if book is not None:
        info["vectors_sha256"] = book.sha256
        # 字典要到 M1 才内嵌；这里显式写"未内嵌"，不留空字段让人误读。
        info["dict_version"] = None
    return info


def _version():
    from bpreflight import __version__

    return __version__


def run(payload, input_info, strict_thresholds=False, with_timestamp=False):
    """执行一次审计，返回 `Report`。

    M0：只装载阈值（顺带验证安装完整性）+ 落 pending finding。
    """
    book = thresholds.load_book()
    findings = [_pending_finding()]

    warnings = []
    skipped = []
    unverified = book.unverified_keys()
    if unverified and strict_thresholds:
        # §8.2：--strict-thresholds 时报告首屏必须打一行提示"此判定基于未核阈值"。
        warnings.append(
            "THRESHOLDS: unverified ({})".format(", ".join(unverified))
        )
    elif unverified:
        warnings.append(
            "THRESHOLDS: unverified ({}) — unverified thresholds are downgraded to warn "
            "unless --strict-thresholds".format(", ".join(unverified))
        )

    # 输入缺 M3 所需参数时**不静默补默认值**（§8.9 G3）：显式登记为 skipped，
    # 而不是产出一条假装判过的结论。
    missing = input_mod.missing_fields(payload)
    if missing:
        skipped.append("input_incomplete:" + ",".join(missing))

    return Report(
        findings=findings,
        input_info=input_info,
        tools_info=_tools_info(book, not with_timestamp),
        skipped=skipped,
        strict_thresholds=strict_thresholds,
        deterministic=not with_timestamp,
        warnings=warnings,
    )


def describe_environment():
    """`--version` / 诊断用：报告解释器与包路径，便于区分"哪个通道跑的"。"""
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "data_dir": paths.DATA_DIR,
    }
