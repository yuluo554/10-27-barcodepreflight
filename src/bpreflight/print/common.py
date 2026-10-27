"""Shared plumbing for the five M3 checks: fixed-point formatting, parsing, and the
single place where "unverified gen-spec threshold" downgrades an `error` to `warn`.

Why a shared module: the downgrade rule must be written exactly once
(`data/README.md` §8.2). If each check rolled its own `if status != verified: ...`,
`--strict-thresholds` would eventually be honoured by four checks out of five.

Two categories, never mixed (K8):

  * **gen-spec** — a standard number this milestone could not verify. Carries
    `status`; an `error` derived from it downgrades to `warn` unless
    `--strict-thresholds`.
  * **engineering-heuristic** — this tool's own probe (dots per module, contrast,
    wavelength delta). No `status`, `threshold_status` is `not-applicable`, the
    severity never moves.
"""

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

from bpreflight import severity as sev
from bpreflight.report.model import (
    BASIS_ENGINEERING,
    BASIS_GEN_SPEC,
    THRESHOLD_NOT_APPLICABLE,
    THRESHOLD_UNVERIFIED,
    Finding,
)

MODULE = "M3"

#: Three decimals, half-up: the report's fixed-point contract (`data/README.md` §8.7,
#: K7). A string, so it is not a numeric threshold literal.
THREE_PLACES = Decimal("0.001")


class PrintInputError(ValueError):
    """A print parameter is present but not a usable number (-> `input_incomplete`)."""


def fixed(value):
    """Render a number as a 3-decimal fixed-point string (`"1.559"`, #C7)."""
    return str(Decimal(value).quantize(THREE_PLACES, rounding=ROUND_HALF_UP))


def as_decimal(raw, field):
    """Parse a spec value into `Decimal`. Strings and ints are both accepted.

    Rejects bool / None / non-finite / non-numeric instead of guessing — a spec
    that says `"x_dimension_mm": "abc"` must not become `0`.
    """
    if isinstance(raw, bool) or raw is None:
        raise PrintInputError("{} must be a number, got {!r}".format(field, raw))
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise PrintInputError("{} is not a number: {!r}".format(field, raw))
    if not value.is_finite():
        raise PrintInputError("{} must be finite, got {!r}".format(field, raw))
    return value


def ceil_decimal(value):
    """Round up to an integer `Decimal` (used for "the next usable DPI")."""
    return Decimal(value).to_integral_value(rounding=ROUND_CEILING)


# --------------------------------------------------------------------------- #
# findings
# --------------------------------------------------------------------------- #


def engineering_finding(finding_id, severity, observed, target, ref, quote, fix=None,
                        threshold=None):
    """An `engineering-heuristic` finding: no status, no downgrade (K8)."""
    return Finding(
        id=finding_id,
        module=MODULE,
        severity=severity,
        observed=observed,
        target=target,
        threshold=threshold,
        threshold_status=THRESHOLD_NOT_APPLICABLE,
        basis=BASIS_ENGINEERING,
        evidence={"kind": "engineering-heuristic", "ref": ref, "quote": quote},
        fix=fix,
    )


def gen_spec_finding(book, finding_id, base_severity, observed, target, entry, ref,
                     strict_thresholds, fix=None, threshold=None):
    """A `gen-spec` finding, downgraded to `warn` while its threshold is unverified.

    `entry` is the raw threshold object from the bundled vector, so the status that
    drives the downgrade is the same object the report cites.

    The structure tier (`quiet_zone_absent`) does **not** come through here: it
    compares no threshold, so it builds its finding directly with
    `threshold_status: "not-applicable"` (`print/quiet_zone.py`). Keeping it out of
    this helper is what makes "the downgrade cannot touch the zero-quiet-zone error"
    a structural fact rather than a flag someone must remember to pass.
    """
    status = book.status_of(entry)
    severity = base_severity
    if base_severity == sev.ERROR and status == THRESHOLD_UNVERIFIED and not strict_thresholds:
        severity = sev.WARN
    return Finding(
        id=finding_id,
        module=MODULE,
        severity=severity,
        observed=observed,
        target=target,
        threshold=threshold,
        threshold_status=status,
        basis=BASIS_GEN_SPEC,
        evidence={
            "kind": "vector",
            "ref": ref,
            "quote": entry.get("source", ""),
        },
        fix=fix,
    )
