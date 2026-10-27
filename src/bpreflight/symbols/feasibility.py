"""M2 · 符号可行性：结构判定（不做真实编码、不渲染图像）。

三段判据，全部由 `data/vectors/symbol_profiles.json` 驱动：

  1. **字符集 ⊆** —— 数据里每个字符都在该符号某个模式的字符集里；
  2. **长度 ∈** —— 定长符号必须精确匹配（含校验位），变长符号必须落在 `[min, max]`；
  3. **模式可覆盖** —— 贪心切分，固定优先级 **longest-first**（`tie_break` 落在 plan 里）。

输出 `FeasibilityResult(findings, skipped, plan)`。`plan` 只在**可编码**时产出：
`{symbol, mode, segments[], total_modules, checksum, tie_break, profile_version}`。
"不可"结论必须点名原因（字符集 / 长度 / 结构 / 模式），不写"国家前缀"这类需要
GEPIR 联网才能判的措辞（`plan/01` §M2 验收）。

三条纪律：

  · 判定模块**不读文件**：`ProfileBook` 由 `pipeline` 装载后传入（与 M1 的
    `validators.validate_element_string` 同一性质）；
  · 校验位**不复制**：GS1 校验位一律调 `gs1/checksum.py`；
  · 未核规则（`status != verified`）派生的 finding 默认降级为 `warn`，
    `--strict-thresholds` 恢复 `error`（`data/README.md` §8.2 同一口径）。
"""

from bpreflight import severity as sev
from bpreflight.gs1 import checksum
from bpreflight.gs1.dictionary import FNC1
from bpreflight.report.model import BASIS_VECTOR, Finding
from bpreflight.symbols import profiles as profiles_mod

MODULE = "M2"

SKIP_DATA_UNPARSED = "symbol_data_unparsed"
SKIP_GS1_2D_NOT_MODELLED = "gs1_2d_fnc1_not_modelled"


class FeasibilityResult(object):
    """Findings + "could not judge this" channel + the encoding plan (only when feasible)."""

    __slots__ = ("findings", "skipped", "plan")

    def __init__(self, findings, skipped, plan):
        self.findings = list(findings)
        self.skipped = list(skipped)
        self.plan = plan


# --------------------------------------------------------------------------- #
# 数据面
# --------------------------------------------------------------------------- #


def _element_stream(elements):
    """Rebuild the encoded character stream from parsed elements.

    GS1-128 encodes `AI + value` with FNC1 (GS) after variable-length values —
    not the bracketed HRI text. Doing this here keeps the plan's segment text
    identical to what a carrier actually transmits.
    """
    parts = []
    last = len(elements) - 1
    for index, element in enumerate(elements):
        parts.append(element.ai)
        parts.append(element.value)
        if element.aid.fixed_length is None and index != last:
            parts.append(FNC1)
    return "".join(parts)


def _retail_payload(book, profile, elements, identifier, strict_thresholds):
    """Retail GTIN symbols carry a single GTIN; AI 01 is N14 by definition.

    A `(01)` element is a GTIN-14; the retail form is the same GTIN with its
    fixed zero padding removed (GTIN-13 = strip 1, GTIN-12 = strip 2,
    GTIN-8 = strip 6). The padding must actually be zeros — otherwise the data
    is a *different* GTIN, not a shorter one. This is a structure reason, never
    a "national prefix" claim (prefix ownership needs GEPIR, a non-goal).
    """
    mapping = profile.gtin_map
    if elements is None:
        return identifier, []

    if len(elements) != 1 or elements[0].ai != "01":
        first_ai = elements[0].ai if elements else "?"
        finding = _make_finding(
            book,
            profile,
            "symbol_structure_mismatch",
            sev.ERROR,
            "this symbol carries a single GTIN; the element string has {} element(s), "
            "first AI {!r}".format(len(elements), first_ai),
            "structure",
            {
                "kind": "supply_identifier",
                "to": "identifier",
                "unit": "field",
                "rationale": "retail GTIN symbols carry one GTIN, not an AI element string",
            },
            mapping["status"],
            mapping["source"],
            "gtin_map",
            strict_thresholds,
        )
        return None, [finding]

    value = elements[0].value
    if len(value) != mapping["from_length"]:
        finding = _make_finding(
            book,
            profile,
            "symbol_length_mismatch",
            sev.ERROR,
            "AI 01 value has {} characters; a GTIN element is {}".format(
                len(value), mapping["from_length"]
            ),
            "structure",
            {
                "kind": "adjust_data_length",
                "to": str(mapping["from_length"]),
                "unit": "characters",
                "rationale": "AI 01 is a fixed-length GTIN",
            },
            mapping["status"],
            mapping["source"],
            "gtin_map",
            strict_thresholds,
        )
        return None, [finding]

    width = mapping["zero_padding_width"]
    padding = value[:width]
    if padding != "0" * width:
        finding = _make_finding(
            book,
            profile,
            "symbol_structure_mismatch",
            sev.ERROR,
            "GTIN-14 {} begins with {!r}, not {} zero(s); it has no {} form".format(
                value, padding, width, profile.name
            ),
            "structure",
            {
                "kind": "use_matching_gtin_family",
                "to": "{}-digit GTIN".format(mapping["target_length"]),
                "unit": "identifier",
                "rationale": "the GTIN-14 zero padding must be zeros to shorten the GTIN",
            },
            mapping["status"],
            mapping["source"],
            "gtin_map",
            strict_thresholds,
        )
        return None, [finding]

    return value[width:], []


# --------------------------------------------------------------------------- #
# 字符集与切分
# --------------------------------------------------------------------------- #


def _charset_covers(charset, char):
    characters = charset.get("characters")
    if characters is not None and char in characters:
        return True
    ranges = charset.get("ranges")
    if ranges:
        code = ord(char)
        for low, high in ranges:
            if low <= code <= high:
                return True
    return False


def _union_covers(charsets, char):
    for charset in charsets.values():
        if _charset_covers(charset, char):
            return True
    return False


def _segments_for(text, profile):
    """Greedy longest-first segmentation; returns None if no mode covers the head.

    Determinism: the winner is `(run length, -priority, name)` — longest run
    first (the mandated `tie_break`), then the profile's mode priority, then the
    mode name. Same input ⇒ same segments, always.
    """
    charsets = profile.charsets
    modes = profile.modes
    segments = []
    cursor = 0
    total = len(text)
    while cursor < total:
        best = None
        for mode in modes:
            charset = charsets[mode["charset"]]
            run = 0
            while cursor + run < total and _charset_covers(charset, text[cursor + run]):
                run += 1
            group = mode["group_size"]
            if mode.get("requires_full_groups") and group > 1:
                run -= run % group
            if run < mode["min_run"]:
                continue
            key = (run, -mode["priority"], mode["name"])
            if best is None or key > best[0]:
                best = (key, run, mode)
        if best is None:
            return None
        _, run, mode = best
        segment = {
            "mode": mode["name"],
            "text": text[cursor:cursor + run],
            "characters": run,
        }
        segment.update(_units_for(profile.modules, mode, run))
        segments.append(segment)
        cursor += run
    return segments


def _units_for(area, mode, characters):
    group = mode["group_size"]
    groups = (characters + group - 1) // group
    if area["kind"] == "matrix":
        return {
            "bits": mode["header_bits"] + mode["count_bits"] + mode["group_bits"] * groups
        }
    return {"codewords": groups}


# --------------------------------------------------------------------------- #
# 长度 / 模块数 / 校验位
# --------------------------------------------------------------------------- #


def _length_problem(rule, characters):
    """Return `(finding_id, detail, target_value)`; `(None, None, None)` when it fits."""
    if rule["kind"] == "exact":
        if characters != rule["exact"]:
            return (
                "symbol_length_mismatch",
                "{} characters; this symbol requires exactly {} (including its check "
                "digit); the length does not fit this symbol".format(characters, rule["exact"]),
                str(rule["exact"]),
            )
        return None, None, None
    if characters < rule["min"]:
        return (
            "capacity_exceeded",
            "{} characters; this symbol requires at least {}".format(characters, rule["min"]),
            str(rule["min"]),
        )
    if characters > rule["max"]:
        return (
            "capacity_exceeded",
            "{} characters; this symbol holds at most {}".format(characters, rule["max"]),
            str(rule["max"]),
        )
    return None, None, None


def _total_modules(profile, segments):
    """Return `(total_modules | None, needed_bits | None, largest_bits | None)`."""
    area = profile.modules
    kind = area["kind"]

    if kind == "fixed":
        return area["total"], None, None

    if kind == "code128":
        codewords = 0
        for segment in segments:
            codewords += segment["codewords"]
        switches = len(segments) - 1
        inside = codewords + switches * area["switch_codewords"]
        total = (
            area["start_modules"]
            + inside * area["modules_per_codeword"]
            + area["check_modules"]
            + area["stop_modules"]
        )
        return total, None, None

    if kind == "code39":
        characters = 0
        for segment in segments:
            characters += segment["characters"]
        total = (characters + area["start_stop_characters"]) * area[
            "modules_per_character"
        ] + (characters + 1) * area["inter_character_gap"]
        return total, None, None

    # matrix: pick the smallest modelled size that holds the needed bits
    bits = 0
    for segment in segments:
        bits += segment["bits"]
    rows = sorted(area["table"], key=lambda row: row["data_codewords"])
    largest = rows[-1]["data_codewords"] * area["bits_per_codeword"]
    for row in rows:
        if bits <= row["data_codewords"] * area["bits_per_codeword"]:
            return row["side"] * row["side"], bits, largest
    return None, bits, largest


def _checksum(profile, payload):
    """Record the plan's check digit without a second implementation."""
    rule = profile.checksum
    out = {
        "kind": rule["kind"],
        "value": None,
        "appended": bool(rule.get("appended")),
        "verified": False,
    }
    if rule["kind"] == "gs1" and payload.isdigit():
        out["source"] = "gs1/checksum.py"
        if checksum.gs1_is_valid(payload):
            out["value"] = payload[-1]
            out["verified"] = True
        else:
            out["note"] = (
                "check digit in the data is invalid; M1 reports it as invalid_csum "
                "(single implementation: gs1/checksum.py)"
            )
    else:
        out["note"] = (
            "computed by the encoder; not modelled in M2 "
            "(the only check-digit implementation is gs1/checksum.py)"
        )
    return out


# --------------------------------------------------------------------------- #
# findings
# --------------------------------------------------------------------------- #


def _status_of(rules):
    """`verified` only when every contributing rule is verified."""
    statuses = [rule["status"] for rule in rules]
    if statuses and all(status == profiles_mod.STATUS_VERIFIED for status in statuses):
        return profiles_mod.STATUS_VERIFIED
    return profiles_mod.STATUS_UNVERIFIED


def _make_finding(
    book,
    profile,
    finding_id,
    base_severity,
    observed,
    scope,
    fix,
    status,
    source_key,
    ref_suffix,
    strict_thresholds,
):
    severity = base_severity
    if base_severity == sev.ERROR and status != profiles_mod.STATUS_VERIFIED:
        # 未核规则不得当成硬结论（§8.2）；--strict-thresholds 时恢复 error。
        if not strict_thresholds:
            severity = sev.WARN
    return Finding(
        id=finding_id,
        module=MODULE,
        severity=severity,
        observed=observed,
        target="symbol:{}:{}".format(profile.name, scope),
        ai_position=-1,
        threshold=None,
        threshold_status=status,
        basis=BASIS_VECTOR,
        evidence={
            "kind": "vector",
            "ref": "symbol_profiles.json#symbols.{}.{}".format(profile.name, ref_suffix),
            "quote": book.source_text(source_key),
        },
        fix=dict(fix) if fix is not None else None,
    )


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def assess(book, symbol, identifier=None, elements=None, strict_thresholds=False):
    """Judge whether `identifier` / `elements` can be carried by `symbol`.

    `book` is the loaded `ProfileBook`; `elements` are the parsed GS1 elements
    from `gs1/elements.py` (or None when the input used `identifier`).
    """
    profile = book.require(symbol)
    findings = []
    skipped = []

    if elements is not None and not elements:
        # 元素串一个元素都没解析出来（M1 已报 unknown_ai / malformed）：
        # 符号层没有数据可判，不许拿空串去算长度。
        return FeasibilityResult(findings, [SKIP_DATA_UNPARSED], None)

    if profile.data_shape == "retail-gtin":
        payload, problems = _retail_payload(
            book, profile, elements, identifier, strict_thresholds
        )
        findings.extend(problems)
        if payload is None:
            return FeasibilityResult(findings, skipped, None)
    elif elements is not None:
        payload = _element_stream(elements)
        if not payload:
            return FeasibilityResult(findings, [SKIP_DATA_UNPARSED], None)
    else:
        payload = identifier
        ai = profile.identifier_ai
        if ai:
            payload = ai + payload

    blocking = False

    offending = sorted(
        {char for char in payload if not _union_covers(profile.charsets, char)}
    )
    if offending:
        blocking = True
        status = _status_of(profile.charsets.values())
        first_source = profile.charsets[sorted(profile.charsets)[0]]["source"]
        findings.append(
            _make_finding(
                book,
                profile,
                "symbol_charset_violation",
                sev.ERROR,
                "characters {} are outside the {} character set(s)".format(
                    "".join(repr(char) for char in offending), symbol
                ),
                "charset",
                {
                    "kind": "replace_out_of_charset_characters",
                    "to": ", ".join(sorted(profile.charsets)),
                    "unit": "character-set",
                    "rationale": "every character must fit one of the symbol's modes",
                },
                status,
                first_source,
                "charsets",
                strict_thresholds,
            )
        )

    length_id, detail, target_value = _length_problem(profile.length, len(payload))
    if detail is not None:
        blocking = True
        rule = profile.length
        findings.append(
            _make_finding(
                book,
                profile,
                length_id,
                sev.ERROR,
                detail,
                "length",
                {
                    "kind": "adjust_data_length",
                    "to": target_value,
                    "unit": "characters",
                    "rationale": "symbol capacity / fixed length from the profile table",
                },
                rule["status"],
                rule["source"],
                "length",
                strict_thresholds,
            )
        )

    gs1_mode = profile.gs1["mode"]
    if gs1_mode == "requires-fnc1-flag":
        # 字符层面仍可编码（plan 照出），但这不是 GS1 数据——finding 说清楚。
        findings.append(
            _make_finding(
                book,
                profile,
                "gs1_data_missing_fnc1",
                sev.ERROR,
                "GS1 data supplied; {} carries no FNC1 flag, so the data would not be "
                "read as GS1".format(symbol),
                "gs1",
                {
                    "kind": "use_gs1_symbol",
                    "to": "gs1-128",
                    "unit": "symbol",
                    "rationale": "GS1 data is marked by FNC1 in the first symbol position",
                },
                profile.gs1["status"],
                profile.gs1["source"],
                "gs1",
                strict_thresholds,
            )
        )
    elif gs1_mode == "unsupported":
        # 同上：符号能编码这些字符，但没有 GS1 模式；plan 仍按纯数据编码给出。
        findings.append(
            _make_finding(
                book,
                profile,
                "symbol_structure_mismatch",
                sev.ERROR,
                "{} has no GS1 data mode; GS1 element data cannot be carried as GS1 "
                "in this symbol".format(symbol),
                "gs1",
                {
                    "kind": "use_gs1_symbol",
                    "to": "gs1-128",
                    "unit": "symbol",
                    "rationale": "the symbol has no GS1 mode at all",
                },
                profile.gs1["status"],
                profile.gs1["source"],
                "gs1",
                strict_thresholds,
            )
        )
    elif gs1_mode == "not-modelled":
        skipped.append(SKIP_GS1_2D_NOT_MODELLED)

    if blocking:
        return FeasibilityResult(findings, skipped, None)

    segments = _segments_for(payload, profile)
    if segments is None:
        status = _status_of(profile.modes)
        findings.append(
            _make_finding(
                book,
                profile,
                "symbol_structure_mismatch",
                sev.ERROR,
                "the data cannot be split into any supported mode of {}".format(symbol),
                "mode",
                {
                    "kind": "rewrite_data",
                    "to": "characters covered by the symbol's modes",
                    "unit": "data",
                    "rationale": "no mode covers the head of the data",
                },
                status,
                profile.modes[0]["source"],
                "modes",
                strict_thresholds,
            )
        )
        return FeasibilityResult(findings, skipped, None)

    total_modules, needed_bits, largest_bits = _total_modules(profile, segments)
    if total_modules is None:
        status = _status_of([profile.modules])
        findings.append(
            _make_finding(
                book,
                profile,
                "capacity_exceeded",
                sev.ERROR,
                "needs {} bits; the largest modelled {} size holds {} bits".format(
                    needed_bits, symbol, largest_bits
                ),
                "capacity",
                {
                    "kind": "shorten_data",
                    "to": str(largest_bits),
                    "unit": "bits",
                    "rationale": "size/capacity table from the profile (unverified)",
                },
                status,
                profile.modules["source"],
                "modules",
                strict_thresholds,
            )
        )
        return FeasibilityResult(findings, skipped, None)

    if len(segments) > 1:
        findings.append(
            _make_finding(
                book,
                profile,
                "mode_switch_required",
                sev.INFO,
                "{} segments ({})".format(
                    len(segments), " -> ".join(segment["mode"] for segment in segments)
                ),
                "mode",
                None,
                _status_of(profile.modes),
                profile.modes[0]["source"],
                "modes",
                strict_thresholds,
            )
        )

    if len(segments) == 1:
        mode_name = segments[0]["mode"]
    else:
        mode_name = "mixed"
    plan = {
        "symbol": symbol,
        "mode": mode_name,
        "segments": [dict(segment) for segment in segments],
        "total_modules": total_modules,
        "checksum": _checksum(profile, payload),
        "tie_break": book.tie_break,
        "profile_version": book.version,
    }
    return FeasibilityResult(findings, skipped, plan)
