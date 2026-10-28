"""报告的稳定契约：Finding / Report / fingerprint / 排序。

口径来源：`data/README.md` §8.7（报告字段）与 §8.8（verdict 三值）。
渲染层只消费这里的对象，**不得**重算判定（`references/delivery.md` 报告渲染三律）。
"""

import hashlib

from bpreflight import severity as sev

SCHEMA = "bpreflight/1"

#: `threshold_status` 的三个合法取值（§8.2 / §8.9）。
THRESHOLD_VERIFIED = "verified"
THRESHOLD_UNVERIFIED = "unverified"
THRESHOLD_NOT_APPLICABLE = "not-applicable"
THRESHOLD_STATUSES = (
    THRESHOLD_VERIFIED,
    THRESHOLD_UNVERIFIED,
    THRESHOLD_NOT_APPLICABLE,
)

#: `basis` 的合法取值。
BASIS_GEN_SPEC = "gen-spec"
BASIS_ENGINEERING = "engineering-heuristic"
BASIS_OFFICIAL_DICT = "official-dictionary"
BASIS_VECTOR = "vector"
BASES = (BASIS_GEN_SPEC, BASIS_ENGINEERING, BASIS_OFFICIAL_DICT, BASIS_VECTOR)

#: evidence.kind 的合法取值（§8.9 / `plan/01` 全局确定性纪律第 4 条）。
EVIDENCE_KINDS = ("official-source", "dict-line", "vector", "engineering-heuristic")


class ModelError(ValueError):
    """报告模型的契约违规（构造期就报，不留到渲染期）。"""


class Finding(object):
    """一条判定。不可变——渲染层只读，无法就地"修"结论。

    用普通类 + `__slots__` 而非 dataclass：`requires-python >= 3.8`，
    且 `frozen=True` 的 dataclass 在 3.8 里 `__hash__`/`replace` 行为更绕。
    """

    __slots__ = (
        "id",
        "module",
        "severity",
        "observed",
        "target",
        "ai_position",
        "threshold",
        "threshold_status",
        "basis",
        "evidence",
        "fix",
        "source",
    )

    def __init__(
        self,
        id,
        module,
        severity,
        observed,
        target,
        ai_position=-1,
        threshold=None,
        threshold_status=THRESHOLD_NOT_APPLICABLE,
        basis=BASIS_ENGINEERING,
        evidence=None,
        fix=None,
        source=None,
    ):
        if severity not in sev._SEVERITY_ORDER:
            raise ModelError("unknown severity: {!r}".format(severity))
        if threshold_status not in THRESHOLD_STATUSES:
            raise ModelError("unknown threshold_status: {!r}".format(threshold_status))
        if basis not in BASES:
            raise ModelError("unknown basis: {!r}".format(basis))
        if evidence is None:
            raise ModelError("finding {!r} misses evidence".format(id))
        if evidence.get("kind") not in EVIDENCE_KINDS:
            raise ModelError(
                "finding {!r} evidence.kind invalid: {!r}".format(id, evidence.get("kind"))
            )
        if not evidence.get("ref"):
            raise ModelError("finding {!r} evidence.ref is empty".format(id))
        # warn/error 必须给可执行 fix（决策 D9）。ok/info 不必。
        if severity in (sev.WARN, sev.ERROR) and not fix:
            raise ModelError("finding {!r} is {} but has no fix".format(id, severity))
        if fix is not None and not _fix_is_actionable(fix):
            raise ModelError(
                "finding {!r} fix is not actionable (needs 'to' or 'min_delta')".format(id)
            )

        object.__setattr__(self, "id", id)
        object.__setattr__(self, "module", module)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "ai_position", ai_position)
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "threshold_status", threshold_status)
        object.__setattr__(self, "basis", basis)
        object.__setattr__(self, "evidence", dict(evidence))
        object.__setattr__(self, "fix", dict(fix) if fix is not None else None)
        object.__setattr__(self, "source", source)

    # ---- 不可变 ----

    def __setattr__(self, name, value):
        raise AttributeError("Finding is immutable")

    def __delattr__(self, name):
        raise AttributeError("Finding is immutable")

    # ---- 派生 ----

    @property
    def fingerprint(self):
        """`sha256(id \\x1f module \\x1f target)[:16]`（§8.7）。

        **不含** severity：阈值状态一改 severity 就变，含它会让跨 run diff 全是噪音。
        **不含**时间戳 / 路径 / 机器名。
        """
        payload = "{}\x1f{}\x1f{}".format(self.id, self.module, self.target)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @property
    def sort_key(self):
        """固定排序键：`(module, ai_position, id)`。

        不用"严重级别优先"：级别会随阈值状态变化，排序跟着变会让两次 run 的 diff 全是噪音。
        """
        return (self.module, self.ai_position, self.id)

    def to_dict(self):
        out = {
            "id": self.id,
            "module": self.module,
            "severity": self.severity,
            "observed": self.observed,
            "target": self.target,
            "ai_position": self.ai_position,
            "threshold": self.threshold,
            "threshold_status": self.threshold_status,
            "basis": self.basis,
            "evidence": dict(self.evidence),
            "fingerprint": self.fingerprint,
        }
        if self.fix is not None:
            out["fix"] = dict(self.fix)
        if self.source is not None:
            out["source"] = self.source
        return out


def _fix_is_actionable(fix):
    """`fix` 必须给目标数值或最小增量（决策 D9）；"请检查你的条码"不算。"""
    if not isinstance(fix, dict):
        return False
    if not fix.get("kind"):
        return False
    has_to = fix.get("to") is not None and fix.get("unit")
    has_delta = fix.get("min_delta") is not None and fix.get("unit")
    return bool(has_to or has_delta)


class Report(object):
    """一次审计的完整结果。渲染层只读。

    `skipped` 是"不可判"的合法通道之一（§8.9）：值形如 `"oracle_absent"` /
    `"requires_capture"` / `"reference_engine_absent"`。**它不是 verdict 的第四个值**。
    """

    def __init__(
        self,
        findings,
        input_info=None,
        tools_info=None,
        skipped=None,
        strict_thresholds=False,
        deterministic=True,
        warnings=None,
        encoding_plan=None,
        timestamp=None,
    ):
        ordered = sorted(findings, key=lambda f: f.sort_key)
        self.findings = tuple(ordered)
        self.input = dict(input_info or {})
        self.tools = dict(tools_info or {})
        self.skipped = tuple(skipped or ())
        self.strict_thresholds = bool(strict_thresholds)
        self.deterministic = bool(deterministic)
        #: ISO-8601 UTC (`--with-timestamp`) or None. Never carries a host name or
        #: a local timezone name (`data/README.md` §8.7): a timestamp that leaks
        #: "which machine, which zone" is exactly the determinism leak D11 guards.
        self.timestamp = timestamp
        #: 报告首屏提示（如 `THRESHOLDS: unverified (quiet_zone.modules_min)`）。
        self.warnings = tuple(warnings or ())
        #: M2 的 `encoding_plan`。只在"可编码"时存在；不可编码时由 findings 说原因。
        self.encoding_plan = dict(encoding_plan) if encoding_plan is not None else None

    @property
    def summary(self):
        counts = {sev.OK: 0, sev.INFO: 0, sev.WARN: 0, sev.ERROR: 0}
        for finding in self.findings:
            counts[finding.severity] += 1
        return counts

    @property
    def verdict(self):
        return sev.verdict_for([f.severity for f in self.findings])

    @property
    def worst_severity(self):
        return sev.worst([f.severity for f in self.findings])

    @property
    def fingerprints(self):
        """用于"两种格式同源"的集合比较，以及跨 run diff。"""
        return sorted(f.fingerprint for f in self.findings)

    @property
    def top_fix(self):
        """最重要的一条修复：取最严重级别里的第一条（已按 sort_key 稳定排序）。"""
        for level in (sev.ERROR, sev.WARN):
            for finding in self.findings:
                if finding.severity == level and finding.fix:
                    return finding
        return None

    def to_dict(self):
        out = {
            "schema": SCHEMA,
            "input": dict(self.input),
            "tools": dict(self.tools),
            "deterministic": self.deterministic,
            "strict_thresholds": self.strict_thresholds,
            "warnings": list(self.warnings),
            "skipped": list(self.skipped),
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "verdict": self.verdict,
        }
        # Timestamp only when the caller asked for it (default: no clock, K10).
        if self.timestamp is not None:
            out["timestamp"] = self.timestamp
        # M2 的 plan 只在"可编码"时出现；不可编码时 findings 说原因（不输出半个计划）。
        if self.encoding_plan is not None:
            out["encoding_plan"] = dict(self.encoding_plan)
        return out
