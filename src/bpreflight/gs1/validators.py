"""The four semantic interpreters plus the structural checks (M1).

Scope is deliberately the four interpreters `plan/00` D1 allows — `req`, `ex`,
`yymmd0`, `csum` — plus the structural checks the dictionary's *specification*
column already expresses as data (charset / length). Everything is driven by
`dictionary.AIDef`; no AI-specific rule is hardcoded here.

Two honesty rules from `data/README.md` §8.9:

  * **G3** — insufficient input is an `error: input_incomplete`, never a
    silently-filled default.
  * A linter the dictionary names but this milestone does not interpret is
    reported as `skipped: linter_not_implemented:<name>`, **not** as a pass.
    Parsing an AI is not the same as having validated its contents.

Date rule (`yymmd0`, transcribed from `lint_yymmd0.c` / `lint_yyyymmd0.c`):

  month must be 01..12; the day is compared against the leap-year-aware month
  length; **DD = 00 is legal and means the last day of that month**. Normalising
  DD=00 must therefore never become "turn date validation off" — the
  `(17)251301` control case exists to prove the rest of the checks still bite.

The two-digit year window is data, not code: `gs1_vectors.json`
`yymmd0.century_resolution`. Using the system clock here would break the
deterministic report (`plan/00` K10).
"""

import calendar

from bpreflight import severity as sev
from bpreflight.gs1 import checksum
from bpreflight.gs1 import dictionary as dict_mod
from bpreflight.gs1.elements import ISSUE_MALFORMED, ISSUE_UNKNOWN_AI
from bpreflight.report.model import (
    BASIS_OFFICIAL_DICT,
    THRESHOLD_NOT_APPLICABLE,
    Finding,
)

MODULE = "M1"

#: Character sets, transcribed from `lint_cset82.c` / `lint_cset39.c` /
#: `lint_csetnumeric.c` and the base64url alphabet named in the table header.
CSET_NUMERIC = "0123456789"
CSET_82 = "!\"%&'()*+,-./0123456789:;<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
CSET_39 = "#-/0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CSET_BASE64URL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

_CHARSETS = {
    "N": ("CSET_NUMERIC", CSET_NUMERIC),
    "X": ("CSET_82", CSET_82),
    "Y": ("CSET_39", CSET_39),
    "Z": ("CSET_BASE64URL", CSET_BASE64URL),
}

#: Interpreted here (the four from `plan/00` D1) plus the date linters that map
#: onto the same `invalid_date` id.
_DATE_LINTERS = ("yymmd0", "yymmdd", "yyyymmd0", "yyyymmdd")
INTERPRETED_LINTERS = ("csum",) + _DATE_LINTERS

#: Linters that need a GS1 Company Prefix allocation lookup to say anything.
#: That lookup is the GEPIR service, i.e. network + authorization, which
#: `plan/01` §7 lists as a non-goal — so these are reported as "cannot judge",
#: never as a pass (`data/README.md` §8.9 G2).
GCP_LOOKUP_LINTERS = ("gcppos1", "gcppos2")
SKIP_GCP_LOOKUP = "gcp_lookup_unavailable"

#: Date kinds: linter name -> (allows DD=00, year digits). Month/day are always
#: two digits each, so the total width follows from the year width.
_DATE_KINDS = {
    "yymmd0": (True, 2),
    "yymmdd": (False, 2),
    "yyyymmd0": (True, 4),
    "yyyymmdd": (False, 4),
}

_MMDD_WIDTH = 4

DICT_REF_PREFIX = "gs1-syntax-dictionary/gs1-syntax-dictionary.txt"


class ValidationResult(object):
    """Findings plus the "could not judge this" channel for one element string."""

    __slots__ = ("findings", "skipped")

    def __init__(self, findings, skipped):
        self.findings = list(findings)
        self.skipped = list(skipped)


def dict_version():
    """Identity of the table the report names (`dict_version`)."""
    from bpreflight.gs1 import dictionary as dictionary_mod

    return dictionary_mod.load_manifest()["dict_version"]


def _dict_evidence(aid):
    """`dict-line` evidence pointing at the exact vendored line."""
    return {
        "kind": "dict-line",
        "ref": "{}:{}".format(DICT_REF_PREFIX, aid.source_line),
        "quote": aid.source_text.strip(),
    }


def _source_evidence(ref, quote):
    return {"kind": "official-source", "ref": ref, "quote": quote}


def _finding(id, severity, observed, target, ai_position, evidence, fix=None, threshold=None):
    return Finding(
        id=id,
        module=MODULE,
        severity=severity,
        observed=observed,
        target=target,
        ai_position=ai_position,
        threshold=threshold,
        threshold_status=THRESHOLD_NOT_APPLICABLE,
        basis=BASIS_OFFICIAL_DICT,
        evidence=evidence,
        fix=fix,
    )


# --------------------------------------------------------------------------- #
# structural: split a field value across the dictionary's components
# --------------------------------------------------------------------------- #


def split_components(aid, value):
    """Split `value` across `aid.components`.

    Returns `(parts, problem)` where `parts` is a list of `(index, Component,
    text)` and `problem` is None or a short reason string. Only the final
    component may have variable length (per the table header), so a variable
    component consumes the remainder.
    """
    parts = []
    cursor = 0
    remaining = len(value)
    for index, component in enumerate(aid.components):
        left = remaining - cursor
        if component.optional and left == 0:
            continue
        if component.is_fixed:
            want = component.min_length
            if left < want:
                if component.optional:
                    continue
                return parts, "component {} needs {} characters, value has {}".format(
                    index, want, left
                )
            text = value[cursor:cursor + want]
            cursor += want
        else:
            # Variable length: the remainder belongs to this (final) component.
            if left < component.min_length:
                return parts, "component {} needs at least {} characters, value has {}".format(
                    index, component.min_length, left
                )
            text = value[cursor:]
            cursor = remaining
        parts.append((index, component, text))
    if cursor != remaining:
        return parts, "{} trailing characters did not match any component".format(
            remaining - cursor
        )
    return parts, None


# --------------------------------------------------------------------------- #
# dates
# --------------------------------------------------------------------------- #


def resolve_date(value, kind, century_resolution):
    """Validate one date field.

    Returns `(status, normalized, detail)` with status in
    `{"ok", "dd00", "invalid_date"}`. `normalized` is `YYYY-MM-DD` for the two
    success statuses.
    """
    allows_dd00, year_width = _DATE_KINDS[kind]
    expected_digits = year_width + _MMDD_WIDTH
    if len(value) != expected_digits or not value.isdigit():
        return "invalid_date", None, "expected {} digits, got {!r}".format(
            expected_digits, value
        )

    year_text = value[:year_width]
    month_text = value[year_width:year_width + 2]
    day_text = value[year_width + 2:]

    if year_width == 2:
        year = _expand_two_digit_year(int(year_text), century_resolution)
    else:
        year = int(year_text)

    month = int(month_text)
    day = int(day_text)

    try:
        last_day = calendar.monthrange(year, month)[1]
    except (ValueError, calendar.IllegalMonthError):
        return "invalid_date", None, "month {} is outside 01..12".format(month_text)

    if day == 0:
        if not allows_dd00:
            return "invalid_date", None, "day 00 is not permitted for {}".format(kind)
        return "dd00", "{:04d}-{:02d}-{:02d}".format(year, month, last_day), "DD=00 -> last day"

    if day > last_day:
        return "invalid_date", None, "day {} exceeds {} for {:04d}-{:02d}".format(
            day, last_day, year, month
        )
    return "ok", "{:04d}-{:02d}-{:02d}".format(year, month, day), ""


def _expand_two_digit_year(two_digit, resolution):
    """Expand YY the way `lint_yymmd0.c` does when CURRENT_YEAR is pinned."""
    reference = resolution["reference_year_yy"]
    window = resolution["century_window"]
    centuries = resolution["centuries"]
    offset = two_digit - reference
    if offset >= window + 1:
        century = centuries["high"]
    elif offset > -(window):
        century = centuries["mid"]
    else:
        century = centuries["low"]
    return century * 100 + two_digit


# --------------------------------------------------------------------------- #
# per-element checks
# --------------------------------------------------------------------------- #


def _check_structure(element, result, resolution):
    """Charset + length + the interpreted linters for one element."""
    aid = element.aid
    position = element.position
    value = element.value
    evidence = _dict_evidence(aid)

    if len(value) < aid.min_length or len(value) > aid.max_length:
        expected = (
            str(aid.min_length)
            if aid.min_length == aid.max_length
            else "{}-{}".format(aid.min_length, aid.max_length)
        )
        result.findings.append(
            _finding(
                "invalid_length",
                sev.ERROR,
                "{} characters".format(len(value)),
                "ai:{}:length".format(aid.ai),
                position,
                evidence,
                fix={
                    "kind": "adjust_value_length",
                    "to": expected,
                    "unit": "characters",
                    "rationale": "dictionary declares {!r} for this AI".format(
                        _spec_text(aid)
                    ),
                },
            )
        )
        # A length violation makes the component split meaningless: stop here
        # rather than emitting derived nonsense about shifted fields.
        return

    parts, problem = split_components(aid, value)
    if problem is not None:
        result.findings.append(
            _finding(
                "invalid_length",
                sev.ERROR,
                problem,
                "ai:{}:components".format(aid.ai),
                position,
                evidence,
                fix={
                    "kind": "adjust_value_length",
                    "to": "{}-{}".format(aid.min_length, aid.max_length),
                    "unit": "characters",
                    "rationale": "value does not fill the dictionary's component layout",
                },
            )
        )
        return

    for index, component, text in parts:
        _check_charset(aid, index, component, text, position, evidence, result)
        for linter in component.linters:
            if linter == "csum":
                _check_csum(aid, index, text, position, evidence, result)
            elif linter in _DATE_KINDS:
                _check_date(aid, index, linter, text, position, evidence, result, resolution)
            elif linter in GCP_LOOKUP_LINTERS:
                # Needs a GCP allocation lookup (GEPIR) to say anything at all;
                # that is a declared non-goal. Reported as "cannot judge".
                result.skipped.append(SKIP_GCP_LOOKUP)
            elif linter not in INTERPRETED_LINTERS:
                result.skipped.append("linter_not_implemented:" + linter)


def _spec_text(aid):
    return " ".join(
        ("[" if c.optional else "")
        + c.type
        + ("" if c.is_fixed else "..")
        + str(c.max_length)
        + ("]" if c.optional else "")
        for c in aid.components
    )


def _check_charset(aid, index, component, text, position, evidence, result):
    name, allowed = _CHARSETS[component.type]
    bad = sorted({char for char in text if char not in allowed})
    if not bad:
        return
    result.findings.append(
        _finding(
            "invalid_charset",
            sev.ERROR,
            "characters {} are outside {}".format(
                "".join(repr(char) for char in bad), name
            ),
            "ai:{}:{}:charset".format(aid.ai, index),
            position,
            evidence,
            fix={
                "kind": "replace_out_of_charset_characters",
                "to": name,
                "unit": "character-set",
                "rationale": "this component is a {!r} field".format(component.type),
            },
        )
    )


def _check_csum(aid, index, text, position, evidence, result):
    if len(text) < 2 or not text.isdigit():
        # Charset/length problems already reported; a check digit over garbage
        # would be a second, derived complaint.
        return
    if checksum.gs1_is_valid(text):
        return
    corrected = text[:-1] + checksum.gs1_check_digit(text[:-1])
    result.findings.append(
        _finding(
            "invalid_csum",
            sev.ERROR,
            "check digit {!r}".format(text[-1]),
            "ai:{}:{}:csum".format(aid.ai, index),
            position,
            _source_evidence(
                "gs1-syntax-dictionary/src/lint_csum.c",
                "parity = (10 - parity % 10) % 10; if (parity + '0' != data[data_len - 1]) "
                "-> INCORRECT_CHECK_DIGIT",
            ),
            fix={
                "kind": "recompute_check_digit",
                "to": corrected,
                "unit": "digits",
                "from": text,
                "rationale": "rule: data/README.md 8.1 (single implementation in gs1/checksum.py)",
            },
        )
    )


def _check_date(aid, index, kind, text, position, evidence, result, resolution=None):
    from bpreflight.gs1 import vectors as vectors_mod

    resolution = resolution or vectors_mod.load_century_resolution()
    status, normalized, detail = resolve_date(text, kind, resolution)
    if status == "ok":
        return
    if status == "dd00":
        result.findings.append(
            _finding(
                "dd00_last_day_of_month",
                sev.INFO,
                "{} -> {}".format(text, normalized),
                "ai:{}:{}:date".format(aid.ai, index),
                position,
                evidence,
            )
        )
        return
    result.findings.append(
        _finding(
            "invalid_date",
            sev.ERROR,
            "{} ({})".format(text, detail),
            "ai:{}:{}:date".format(aid.ai, index),
            position,
            evidence,
            fix={
                "kind": "set_valid_calendar_date",
                "to": "valid {} for {}".format(kind, aid.ai),
                "unit": "date",
                "rationale": detail,
            },
        )
    )


# --------------------------------------------------------------------------- #
# element-string level checks: req / ex / unknown
# --------------------------------------------------------------------------- #


def _check_presence(elements, result):
    """`req` (OR over groups, AND inside a group) and `ex` (mutual exclusion)."""
    present = [element.ai for element in elements]
    for element in elements:
        aid = element.aid
        if aid.req_groups and not any(
            all(member in present for member in group) for group in aid.req_groups
        ):
            alternatives = " or ".join("+".join(group) for group in aid.req_groups)
            result.findings.append(
                _finding(
                    "missing_required_ai",
                    sev.ERROR,
                    "{} present, requires {}".format(aid.ai, alternatives),
                    "ai:{}:req".format(aid.ai),
                    element.position,
                    _dict_evidence(aid),
                    fix={
                        "kind": "add_required_ai",
                        "to": alternatives,
                        "unit": "ai",
                        "rationale": "req attribute; comma = any-of (OR), '+' = all-of (AND)",
                    },
                )
            )
        for pattern in aid.ex_patterns:
            for other in elements:
                if other is element:
                    continue
                if not dict_mod.ai_pattern_matches(pattern, other.ai):
                    continue
                result.findings.append(
                    _finding(
                        "mutually_exclusive_ai",
                        sev.ERROR,
                        "({}) present alongside ({}), which matches ex={}".format(
                            aid.ai, other.ai, pattern
                        ),
                        "ai:{}:ex:{}".format(aid.ai, other.ai),
                        element.position,
                        _dict_evidence(aid),
                        fix={
                            "kind": "remove_conflicting_ai",
                            "to": other.ai,
                            "unit": "ai",
                            "rationale": "ex attribute forbids this pairing",
                        },
                    )
                )


def _check_parse_issues(issues, result):
    """Unknown AIs and unsplittable strings.

    An unknown AI is a data error (`unknown_ai`). A string we cannot split at
    all is surfaced as `invalid_length`, because the field boundaries are what
    failed — not "an AI the dictionary does not know".
    """
    for issue in issues:
        if issue.kind == ISSUE_UNKNOWN_AI:
            result.findings.append(
                _finding(
                    "unknown_ai",
                    sev.ERROR,
                    "AI {!r} is not in the bundled dictionary ({})".format(
                        issue.ai, dict_version()
                    ),
                    "ai:{}:unknown".format(issue.ai or "?"),
                    issue.position,
                    _source_evidence(
                        DICT_REF_PREFIX,
                        "AI {!r} does not appear in the bundled table".format(issue.ai),
                    ),
                    fix={
                        "kind": "replace_with_registered_ai",
                        "to": "an AI present in the bundled dictionary",
                        "unit": "ai",
                        "rationale": issue.detail or "unknown AI",
                    },
                )
            )
        elif issue.kind == ISSUE_MALFORMED:
            result.findings.append(
                _finding(
                    "invalid_length",
                    sev.ERROR,
                    issue.detail or "element string could not be split",
                    "element:{}:parse".format(issue.position),
                    issue.position,
                    _source_evidence(
                        DICT_REF_PREFIX,
                        "element strings are AI + fixed-length value, or AI + value + FNC1",
                    ),
                    fix={
                        "kind": "rewrite_element_string",
                        "to": "AI-prefixed fields separated by FNC1, or (AI)value groups",
                        "unit": "format",
                        "rationale": issue.detail or "unsplittable element string",
                    },
                )
            )


# --------------------------------------------------------------------------- #
# entry points
# --------------------------------------------------------------------------- #


def validate_identifier(identifier, identifier_lengths):
    """Validate a bare identifier (GTIN-8/12/13/14 or SSCC-18).

    Returns a `ValidationResult`. The expected lengths come from data
    (`gs1_vectors.json` `identifier.lengths`), so nothing here hardcodes them.
    """
    findings = []
    skipped = []
    label = identifier_lengths.get(str(len(identifier) if isinstance(identifier, str) else -1))
    evidence = _source_evidence(
        "gs1-syntax-dictionary/src/lint_csum.c + data/README.md 4.2 official vectors",
        "check digit is the last character; weight starts per total length parity",
    )
    if label is None:
        findings.append(
            _finding(
                "invalid_length",
                sev.ERROR,
                "{} characters".format(len(identifier) if isinstance(identifier, str) else 0),
                "identifier:length",
                -1,
                evidence,
                fix={
                    "kind": "adjust_identifier_length",
                    "to": " or ".join(sorted(identifier_lengths)),
                    "unit": "characters",
                    "rationale": "only the documented identifier lengths are supported",
                },
            )
        )
        return ValidationResult(findings, skipped)
    if not identifier.isdigit():
        bad = sorted({char for char in identifier if char not in CSET_NUMERIC})
        findings.append(
            _finding(
                "invalid_charset",
                sev.ERROR,
                "characters {} are outside CSET_NUMERIC".format(
                    "".join(repr(char) for char in bad)
                ),
                "identifier:charset",
                -1,
                evidence,
                fix={
                    "kind": "replace_out_of_charset_characters",
                    "to": "CSET_NUMERIC",
                    "unit": "character-set",
                    "rationale": "{} is a numeric identifier family".format(label),
                },
            )
        )
        return ValidationResult(findings, skipped)
    if not checksum.gs1_is_valid(identifier):
        corrected = identifier[:-1] + checksum.gs1_check_digit(identifier[:-1])
        findings.append(
            _finding(
                "invalid_csum",
                sev.ERROR,
                "check digit {!r}".format(identifier[-1]),
                "identifier:csum",
                -1,
                evidence,
                fix={
                    "kind": "recompute_check_digit",
                    "to": corrected,
                    "unit": "digits",
                    "from": identifier,
                    "rationale": "rule: data/README.md 8.1",
                },
            )
        )
    return ValidationResult(findings, skipped)


def validate_element_string(doc, parse_issues, elements, resolution=None):
    """Run every M1 check over a parsed element string.

    Takes the **parsed** elements rather than the raw text: splitting is
    `elements.py`'s job, and doing it twice is how "the parser and the
    validator disagree" bugs start.
    """
    from bpreflight.gs1 import vectors as vectors_mod

    resolution = resolution or vectors_mod.load_century_resolution()
    result = ValidationResult([], [])
    _check_parse_issues(parse_issues, result)
    for element in elements:
        _check_structure(element, result, resolution)
    if elements:
        _check_presence(elements, result)
    if not elements and not parse_issues:
        result.skipped.append("element_string_empty")
    return result
