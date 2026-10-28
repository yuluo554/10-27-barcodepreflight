"""Markdown 渲染：首屏三段字面固定（`plan/01` §M4、`plan/03` §六）。

首屏三段的**措辞与顺序是契约**，由 `tests/test_report_render.py` 做字面断言：

```
VERDICT: <pass|warn|fail>
FINDINGS: ok=<n> info=<n> warn=<n> error=<n>
TOP FIX: <最重要一条修复的单行摘要，无则 none>
```

本模块是纯排版：不判定、不排序、不重算 fingerprint。
"""

HEADLINE_VERDICT = "VERDICT:"
HEADLINE_FINDINGS = "FINDINGS:"
HEADLINE_TOP_FIX = "TOP FIX:"


def _fix_line(finding):
    """把一条 fix 压成单行摘要（给 TOP FIX 与明细行复用）。"""
    fix = finding.fix or {}
    kind = fix.get("kind", "unspecified")
    unit = fix.get("unit", "")
    suffix = " " + unit if unit else ""
    if fix.get("to") is not None:
        return "{} -> {}{}".format(kind, fix["to"], suffix)
    if fix.get("min_delta") is not None:
        return "{} (+{}{})".format(kind, fix["min_delta"], suffix)
    return kind


def _checksum_line(checksum):
    parts = [str(checksum.get("kind", "none"))]
    if checksum.get("value") is not None:
        parts.append("value=" + str(checksum["value"]))
    if checksum.get("appended"):
        parts.append("appended")
    if checksum.get("verified"):
        parts.append("verified")
    return " ".join(parts)


def render_md(report):
    """返回 (text, filename_hint)。"""
    summary = report.summary
    top = report.top_fix

    lines = []
    lines.append("{} {}".format(HEADLINE_VERDICT, report.verdict))
    lines.append(
        "{} ok={} info={} warn={} error={}".format(
            HEADLINE_FINDINGS,
            summary["ok"],
            summary["info"],
            summary["warn"],
            summary["error"],
        )
    )
    lines.append("{} {}".format(HEADLINE_TOP_FIX, _fix_line(top) if top else "none"))

    # 未核阈值首屏提示（§8.2）：`--strict-thresholds` 下 must 可见。
    for note in report.warnings:
        lines.append(note)
    if report.skipped:
        lines.append("SKIPPED: " + ", ".join(report.skipped))
    # `--with-timestamp` only: the head already says `deterministic: false` in
    # the JSON; the human report repeats the exact moment it was taken (K10).
    if report.timestamp is not None:
        lines.append("TIMESTAMP: {}".format(report.timestamp))

    lines.append("")
    lines.append("## Findings")
    lines.append("")

    if not report.findings:
        lines.append("(no findings)")
    else:
        for finding in report.findings:
            lines.append(
                "- **{}** `{}` [{}] observed={} threshold={} ({})".format(
                    finding.severity,
                    finding.id,
                    finding.module,
                    finding.observed,
                    finding.threshold if finding.threshold is not None else "n/a",
                    finding.threshold_status,
                )
            )
            lines.append("  - basis: `{}`".format(finding.basis))
            if finding.fix is not None:
                lines.append("  - fix: `{}`".format(_fix_line(finding)))
            evidence = finding.evidence
            lines.append(
                "  - evidence: `{}` {}".format(evidence.get("kind"), evidence.get("ref"))
            )
            lines.append("  - fingerprint: `{}`".format(finding.fingerprint))

    # M2 的 encoding plan（只在可编码时存在）；纯排版，不重算任何判定。
    if report.encoding_plan is not None:
        plan = report.encoding_plan
        lines.append("")
        lines.append("## Encoding plan")
        lines.append("")
        lines.append("- `symbol`: {}".format(plan.get("symbol")))
        lines.append("- `mode`: {}".format(plan.get("mode")))
        lines.append("- `total_modules`: {}".format(plan.get("total_modules")))
        lines.append("- `tie_break`: {}".format(plan.get("tie_break")))
        lines.append("- `checksum`: {}".format(_checksum_line(plan.get("checksum") or {})))
        for segment in plan.get("segments", []):
            units = []
            if "codewords" in segment:
                units.append("codewords={}".format(segment["codewords"]))
            if "bits" in segment:
                units.append("bits={}".format(segment["bits"]))
            lines.append(
                "- segment `{}`: {} char(s) {} text={!r}".format(
                    segment.get("mode"),
                    segment.get("characters"),
                    " ".join(units),
                    segment.get("text"),
                )
            )

    lines.append("")
    lines.append("## Input")
    lines.append("")
    for key in sorted(report.input):
        lines.append("- `{}`: {}".format(key, report.input[key]))
    if not report.input:
        lines.append("(none)")

    lines.append("")
    lines.append("## Tools")
    lines.append("")
    for key in sorted(report.tools):
        lines.append("- `{}`: {}".format(key, report.tools[key]))
    if not report.tools:
        lines.append("(none)")

    return "\n".join(lines) + "\n", "bpreflight.md"
