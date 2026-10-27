"""编排：输入 → 判定 → Report。

本棒（M1 数据先行）落地的是**数据层**：内嵌官方 AI 字典 + 校验位 + 四个语义解释器。
`implementation_pending` 已随 M1 同提交退役（决策 D17 的到期条款）——但"退役"不等于
"没有判定也敢说 pass"：现在 **pass 只在真有判定发生时可能出现**，其余一律走
`skipped` / `error: input_incomplete` 两条显式通道（`data/README.md` §8.9）。

因此本模块有三条诚实约束：

1. **输入不足以判定 → `error: input_incomplete`**（§8.9 G3）：既不猜、也不静默补默认值。
2. **未实现的模块 → `skipped: module_not_implemented:<k>`**：M3 尚未落地，报告必须在
   首屏把它标出来，不能让人把 M1/M2 的结论读成"整个条码没问题"。
3. **对照组缺席 → `skipped: reference_engine_absent`**（`plan/05` M1 DoD）：
   同一批向量没有丢给官方 `gs1-syntax-engine` 做过一致性对照，就如实说没做。
4. **符号层的不判也要说**：没给 `symbol` 时 M2 报 `symbol_not_specified`；
   元素串解析不出元素时报 `symbol_data_unparsed`——都不静默滑向 `pass`。

`skipped` 是"不可判"的合法通道，**不是** verdict 的第四个值。
"""

import sys

from bpreflight import input as input_mod
from bpreflight import paths
from bpreflight import severity as sev
from bpreflight import thresholds
from bpreflight.gs1 import dictionary as dictionary_mod
from bpreflight.gs1 import elements as elements_mod
from bpreflight.gs1 import validators as validators_mod
from bpreflight.gs1 import vectors as vectors_mod
from bpreflight.report.model import (
    BASIS_ENGINEERING,
    THRESHOLD_NOT_APPLICABLE,
    Finding,
    Report,
)
from bpreflight.symbols import feasibility as feasibility_mod
from bpreflight.symbols import profiles as profiles_mod

TOOL_NAME = "bpreflight"

#: 已实现的模块。新模块落地时在这里加一个字母，并把对应的
#: `skipped: module_not_implemented:<k>` 消掉（否则报告会说"这个模块还没做"）。
IMPLEMENTED_MODULES = ("M1", "M2")

SKIP_REFERENCE_ENGINE = "reference_engine_absent"


def _input_incomplete_finding(missing):
    """没有可判的输入面时必须产这条 **error**（§8.9 G3）。

    为什么是 error 而不是"空 findings ⇒ pass"：空 findings 会派生出
    `verdict: pass`，而 `pass` 的语义是"这个条码没问题"。没有判定就绝不能走到那里
    （`data/README.md` §8.9 末条：禁止用 pass 表示不知道）。
    等 M3 落地后，只给印刷参数的输入会由 M3 判，这条只在"任何已实现模块都判不了"
    时出现。
    """
    return Finding(
        id="input_incomplete",
        module="M1",
        severity=sev.ERROR,
        observed="missing: " + ", ".join(missing),
        target="input:" + "|".join(missing),
        threshold=None,
        threshold_status=THRESHOLD_NOT_APPLICABLE,
        basis=BASIS_ENGINEERING,
        evidence={
            "kind": "engineering-heuristic",
            "ref": "data/README.md §8.9 G3",
            "quote": "输入参数不足以判定 → 产 error: input_incomplete 并列出缺失字段；"
            "不得用默认值静默补齐",
        },
        fix={
            "kind": "supply_missing_input",
            "to": " or ".join(missing),
            "unit": "field",
            "rationale": "没有输入就没有判定；用默认值补齐等于替用户编数据",
        },
    )


def _module_skips(payload):
    """M3 尚未实现：输入里出现了印刷层的面就把这件事标出来。

    M2 已落地（符号层），不再进 `module_not_implemented`——它的"不可判"由
    `symbol_not_specified` / `symbol_data_unparsed` / `gs1_2d_fnc1_not_modelled`
    三条更具体的通道表达。
    """
    skips = []
    if any(payload.get(name) is not None for name in input_mod.PRINT_FIELDS):
        skips.append("module_not_implemented:M3")
    return skips


def _run_m1(payload, doc, resolution, parsed, parse_issues):
    """数据层判定。返回 `(findings, skipped, judged)`。

    `judged` 为 False 表示输入里没有任何数据层可判的面——调用方据此决定是否
    产 `input_incomplete`，**不能**让它默默变成 `pass`。
    """
    findings = []
    skipped = []
    judged = False

    element_string = payload.get("gs1_element_string")
    identifier = payload.get("identifier")

    if element_string is not None:
        result = validators_mod.validate_element_string(doc, parse_issues, parsed, resolution)
        findings.extend(result.findings)
        skipped.extend(result.skipped)
        # M1 DoD：同一批向量没有交给官方 gs1-syntax-engine 对照过，就如实登记。
        skipped.append(SKIP_REFERENCE_ENGINE)
        judged = True

    if identifier is not None:
        result = validators_mod.validate_identifier(
            identifier, vectors_mod.identifier_lengths()
        )
        findings.extend(result.findings)
        skipped.extend(result.skipped)
        judged = True

    return findings, skipped, judged


def _run_m2(payload, profile_book, parsed, strict_thresholds):
    """符号层判定。返回 `(findings, skipped, plan)`。

    三种"不判"都要说清楚，而不是静默：

    * 有 `symbol` 没数据面 → 不判（M1 的 `input_incomplete` 已点名缺哪个字段）；
    * 有数据面没 `symbol` → `skipped: symbol_not_specified`（不猜目标符号）；
    * 元素串解析不出任何元素 → `symbol_data_unparsed`（M1 已报 unknown_ai/malformed）。
    """
    symbol = payload.get("symbol")
    identifier = payload.get("identifier")
    has_elements = parsed is not None

    if symbol is None:
        if has_elements or identifier is not None:
            return [], ["symbol_not_specified"], None
        return [], [], None
    if not has_elements and identifier is None:
        return [], [], None

    result = feasibility_mod.assess(
        profile_book,
        symbol,
        identifier=identifier,
        elements=parsed,
        strict_thresholds=strict_thresholds,
    )
    return result.findings, result.skipped, result.plan


def _tools_info(doc, book, profile_book, deterministic):
    info = {
        "tool": TOOL_NAME,
        "version": _version(),
        "vectors_sha256": book.sha256 if book is not None else None,
        # 字典身份：`dict_version` 给人读，`dict_sha256` 可独立复算（plan/03 §三）。
        "dict_version": doc.dict_version if doc is not None else None,
        "dict_sha256": doc.sha256 if doc is not None else None,
        # M2 的规则表身份：报告要说清"哪个 profile 表判的"。
        "symbol_profiles_version": profile_book.version if profile_book is not None else None,
        "symbol_profiles_sha256": profile_book.sha256 if profile_book is not None else None,
    }
    if not deterministic:
        info["deterministic"] = False
    return info


def _version():
    from bpreflight import __version__

    return __version__


def _dedup(values):
    """保序去重：同一跳过来自多个元素时，首屏只该出现一次。"""
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def run(payload, input_info, strict_thresholds=False, with_timestamp=False):
    """执行一次审计，返回 `Report`。

    M1：装载字典（哈希校验）+ 阈值册，判定数据层。字典/向量装载失败一律
    向上抛（调用方映射为 exit 3）——**不产判定**，因为"读不到字典"不是关于条码的结论。
    M2：装载符号 profile 表，判定目标符号的结构可行性并产出 `encoding_plan`。
    """
    book = thresholds.load_book()
    doc = dictionary_mod.load()
    resolution = vectors_mod.load_century_resolution()
    profile_book = profiles_mod.load()

    # 元素串只解析一次：M1 的校验与 M2 的字符流用的是同一份元素。
    element_string = payload.get("gs1_element_string")
    if element_string is not None:
        parsed, parse_issues = elements_mod.parse(element_string, doc)
    else:
        parsed, parse_issues = None, None

    findings = []
    skipped = []
    warnings = []

    m1_findings, m1_skipped, judged = _run_m1(
        payload, doc, resolution, parsed, parse_issues
    )
    findings.extend(m1_findings)
    skipped.extend(m1_skipped)
    if not judged:
        # 没有任何已实现模块能判这个输入：绝不静默滑向 pass。
        findings.append(_input_incomplete_finding(list(input_mod.DATA_FIELDS)))

    m2_findings, m2_skipped, encoding_plan = _run_m2(
        payload, profile_book, parsed, strict_thresholds
    )
    findings.extend(m2_findings)
    skipped.extend(m2_skipped)

    unverified = book.unverified_keys()
    if unverified and strict_thresholds:
        # §8.2：--strict-thresholds 时报告首屏必须打一行提示"此判定基于未核阈值"。
        warnings.append("THRESHOLDS: unverified ({})".format(", ".join(unverified)))
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

    skipped.extend(_module_skips(payload))

    return Report(
        findings=findings,
        input_info=input_info,
        tools_info=_tools_info(doc, book, profile_book, not with_timestamp),
        skipped=_dedup(skipped),
        strict_thresholds=strict_thresholds,
        deterministic=not with_timestamp,
        warnings=warnings,
        encoding_plan=encoding_plan,
    )


def describe_environment():
    """`--version` / 诊断用：报告解释器与包路径，便于区分"哪个通道跑的"。"""
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "data_dir": paths.DATA_DIR,
        "implemented_modules": ",".join(IMPLEMENTED_MODULES),
    }