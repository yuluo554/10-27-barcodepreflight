"""M3 orchestration: parse the print spec once, run the five checks, never guess.

The refusal rule is the important one (`data/README.md` §8.9 G3):

  Missing `x_dimension_mm` / `target_dpi` / `quiet_zone_mm` -> **one**
  `error: input_incomplete`, and **no** `quiet_zone_*` / `magnification_*` /
  `raster_*` findings at all. Filling a default would mean judging a barcode the
  user did not describe.

Two further honesty channels, both `skipped` rather than severity:

  * `symbol_not_specified` — print thresholds are per-symbol (quiet zone modules
    differ by symbol), so a spec with print geometry but no `symbol` cannot be
    judged at this layer.
  * `symbol_unsupported:<name>` — a symbol outside the implemented profile table
    cannot supply its quiet-zone rows.

The `color` check is the exception to "no findings without geometry": luminance
contrast is a property of the two colours alone. It runs whenever both colours and
the illumination are present, even if the geometry is incomplete — with no
`magnification_*` / `raster_*` / `quiet_zone_*` conclusions attached.
"""

from bpreflight import input as input_mod
from bpreflight import severity as sev
from bpreflight.print import bar_height, color, common, magnification, quiet_zone, raster

SKIP_SYMBOL_NOT_SPECIFIED = "symbol_not_specified"


class PrintResult(object):
    """Findings + the "could not judge this" channel for the print layer.

    `judged` is what stops "no findings" from being mistaken for "not judged":
    a clean geometry produces **zero** findings and `judged=True`, while a spec
    with print input but a missing field produces `judged=False` plus one
    `input_incomplete`. Without the flag the two cases look identical to the
    caller (`pipeline`), and "no findings" would silently become `pass`.
    """

    __slots__ = ("findings", "skipped", "judged")

    def __init__(self, findings, skipped, judged):
        self.findings = list(findings)
        self.skipped = list(skipped)
        self.judged = bool(judged)


def has_print_input(payload):
    """True when the spec asks for the print layer at all.

    Deliberately excludes `symbol`: it is shared with M2, so a spec with only
    `symbol` + data-layer fields is asking for symbol feasibility, not a print
    audit. Counting it here would turn every clean M1/M2 spec into
    `input_incomplete`.
    """
    return any(payload.get(name) is not None for name in input_mod.PRINT_INPUT_FIELDS)


def _incomplete(missing):
    """The single `error: input_incomplete` for an unusable print spec (§8.9 G3)."""
    return common.engineering_finding(
        "input_incomplete",
        sev.ERROR,
        observed="missing: " + ", ".join(missing),
        target="print:" + "|".join(missing),
        ref="data/README.md §8.9 G3",
        quote="输入参数不足以判定 → 产 error: input_incomplete 并列出缺失字段；"
        "不得用默认值静默补齐",
        fix={
            "kind": "supply_missing_input",
            "to": " or ".join(missing),
            "unit": "field",
            "rationale": "没有输入就没有判定；用默认值补齐等于替用户编数据",
        },
    )


def _parse_quiet_zone(raw):
    """`quiet_zone_mm` may be a scalar (all four sides) or a per-side object."""
    if isinstance(raw, dict):
        return {side: common.as_decimal(raw.get(side, 0), "quiet_zone_mm." + side)
                for side in quiet_zone.SIDES}
    value = common.as_decimal(raw, "quiet_zone_mm")
    return {side: value for side in quiet_zone.SIDES}


def assess(book, profile_book, payload, strict_thresholds=False):
    """Judge the print layer of one spec. Always returns a `PrintResult`.

    `book` is the loaded `ThresholdBook` and `profile_book` the loaded `ProfileBook`
    — both handed in by `pipeline`; this module never opens a data file.
    """
    if not has_print_input(payload):
        return PrintResult([], [], False)

    findings = []
    skipped = []

    # ---- colour: independent of geometry (both colours + illumination only) ----
    bar = payload.get("bar_color")
    space = payload.get("space_color")
    illumination = payload.get("illumination")
    if bar is not None and space is not None and illumination is not None:
        findings.extend(color.check(book, bar, space, illumination))

    # ---- geometry: refuse rather than default (§8.9 G3) ----
    missing = input_mod.missing_fields(payload)
    if missing:
        findings.append(_incomplete(missing))
        return PrintResult(findings, skipped, False)

    symbol = payload.get("symbol")
    if symbol is None:
        skipped.append(SKIP_SYMBOL_NOT_SPECIFIED)
        return PrintResult(findings, skipped, False)
    if symbol not in profile_book.names():
        skipped.append("symbol_unsupported:" + symbol)
        return PrintResult(findings, skipped, False)

    try:
        x_dimension_mm = common.as_decimal(payload.get("x_dimension_mm"), "x_dimension_mm")
        target_dpi = common.as_decimal(payload.get("target_dpi"), "target_dpi")
        quiet_zone_mm = _parse_quiet_zone(payload.get("quiet_zone_mm"))
        bar_height_mm = (
            common.as_decimal(payload.get("bar_height_mm"), "bar_height_mm")
            if payload.get("bar_height_mm") is not None
            else None
        )
    except common.PrintInputError:
        # The field is present but unusable: that is still "not enough to judge",
        # not a licence to substitute a number.
        findings.append(_incomplete(["usable value for the print parameters"]))
        return PrintResult(findings, skipped, False)

    if x_dimension_mm <= 0:
        # §8.3: `<= 0` is `error: x_dimension_missing` — a zero X makes every other
        # ratio divide by zero, so no derived conclusion may follow.
        findings.append(_x_dimension_missing(x_dimension_mm))
        return PrintResult(findings, skipped, False)

    findings.extend(
        quiet_zone.check(book, symbol, quiet_zone_mm, x_dimension_mm, strict_thresholds)
    )
    findings.extend(magnification.check(book, x_dimension_mm, strict_thresholds))
    findings.extend(raster.check(book, x_dimension_mm, target_dpi, strict_thresholds))
    if bar_height_mm is not None:
        findings.extend(
            bar_height.check(book, symbol, bar_height_mm, x_dimension_mm, strict_thresholds)
        )

    return PrintResult(findings, skipped, True)


def _x_dimension_missing(x_dimension_mm):
    return common.engineering_finding(
        "x_dimension_missing",
        sev.ERROR,
        observed="x_dimension_mm = {}".format(common.fixed(x_dimension_mm)),
        target="x_dimension",
        ref="data/README.md §8.3",
        quote="<= 0 or a missing x_dimension_mm -> error: x_dimension_missing",
        fix={
            "kind": "set_x_dimension",
            "to": "> 0.000",
            "unit": "mm",
            "rationale": "every ratio in this module divides by x_dimension_mm",
        },
    )
