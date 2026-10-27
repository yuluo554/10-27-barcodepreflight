"""C1 · quiet zone: the module's "no standard number needed" anchor.

Three tiers, ordered from "needs nothing" to "needs a verified number"
(`data/README.md` §8.2):

| tier | id | condition | needs `modules_min` | severity |
| --- | --- | --- | --- | --- |
| structure | `quiet_zone_absent` | a required side is `quiet_zone_mm == 0` | **no** | always `error` |
| threshold | `quiet_zone_insufficient` | `qz_modules < modules_min` | yes | verified->error / unverified->warn |
| marginal | `quiet_zone_marginal` | `modules_min <= qz < modules_min x factor` | yes | `warn` |

The structure tier is the point of this check. BinaryEye #616 ("the quiet zone is
no longer generated") is a **structure** fact: zero margin is zero margin, and no
unverified GenSpec number may soften it. So `quiet_zone_absent` reads only
`required` (is this side supposed to have a quiet zone at all) and never
`modules_min`.

`required` is a structural fact, not a threshold: for 1D symbols the scanning
sides are left/right; for 2D all four sides carry the finder/timing pattern.
"""

from bpreflight import severity as sev
from bpreflight.print.common import as_decimal, fixed, gen_spec_finding
from bpreflight.report.model import BASIS_GEN_SPEC, THRESHOLD_NOT_APPLICABLE, Finding

#: Side order is fixed so the report and the findings sort are stable.
SIDES = ("left", "right", "top", "bottom")

EVIDENCE_REF = "quiet_zone.json#symbols.{}.{}"


def _absent(symbol, side):
    """Zero quiet zone on a required side: error, unconditionally.

    Built by hand rather than through `gen_spec_finding` on purpose. That helper
    exists to apply the unverified downgrade, and the structure tier must be
    visibly outside it: `threshold_status` is `not-applicable` because **no
    threshold is compared** — the only datum read is `required`, a structure fact.

    Reporting `unverified` here would tell the reader "this error is tentative
    because the number is unverified", which is the opposite of the point: zero
    margin is zero margin whatever the standard says (`data/README.md` §8.2 first
    row). The evidence still cites the row, so provenance is not lost.
    """
    return Finding(
        id="quiet_zone_absent",
        module="M3",
        severity=sev.ERROR,
        observed="0.000 mm on the {} side (this symbol requires a quiet zone there)".format(
            side
        ),
        target="quiet_zone.{}".format(side),
        threshold=None,
        threshold_status=THRESHOLD_NOT_APPLICABLE,
        basis=BASIS_GEN_SPEC,
        evidence={
            "kind": "vector",
            "ref": EVIDENCE_REF.format(symbol, side),
            "quote": "required=true for this side; a zero margin is a structure failure, "
            "not a threshold one",
        },
        fix={
            "kind": "add_quiet_zone",
            "min_delta": "1",
            "unit": "module",
            "rationale": "a zero quiet zone is a structure failure, not a threshold one: "
            "the required side needs a non-zero margin, and no standard number is "
            "needed to see that",
        },
    )


def check(book, symbol, quiet_zone_mm, x_dimension_mm, strict_thresholds):
    """Assess all four sides. Returns a list of findings (possibly empty)."""
    findings = []
    factor = as_decimal(
        book.engineering("quiet_zone_marginal_factor")["value"], "quiet_zone_marginal_factor"
    )

    for side in SIDES:
        entry = book.quiet_zone_entry(symbol, side)
        margin = quiet_zone_mm[side]

        if margin == 0:
            if entry.get("required"):
                findings.append(_absent(symbol, side))
            # A side the symbol does not require (1D top/bottom) may legitimately be 0.
            continue

        modules_min = entry["modules_min"]
        needed = modules_min * x_dimension_mm
        qz_modules = margin / x_dimension_mm

        if qz_modules < modules_min:
            findings.append(
                gen_spec_finding(
                    book,
                    "quiet_zone_insufficient",
                    sev.ERROR,
                    observed="{} modules ({} mm / {} mm X)".format(
                        fixed(qz_modules), fixed(margin), fixed(x_dimension_mm)
                    ),
                    target="quiet_zone.{}".format(side),
                    entry=entry,
                    ref=EVIDENCE_REF.format(symbol, side),
                    strict_thresholds=strict_thresholds,
                    threshold="{} modules".format(modules_min),
                    fix={
                        "kind": "increase_quiet_zone",
                        "to": fixed(needed),
                        "unit": "mm",
                        "from": fixed(margin),
                        "rationale": "modules_min x x_dimension = {} x {}".format(
                            modules_min, fixed(x_dimension_mm)
                        ),
                    },
                )
            )
            continue

        marginal_limit = needed * factor
        if margin < marginal_limit:
            findings.append(
                gen_spec_finding(
                    book,
                    "quiet_zone_marginal",
                    sev.WARN,
                    observed="{} modules ({} mm); the minimum is {} modules".format(
                        fixed(qz_modules), fixed(margin), modules_min
                    ),
                    target="quiet_zone.{}".format(side),
                    entry=entry,
                    ref=EVIDENCE_REF.format(symbol, side),
                    strict_thresholds=strict_thresholds,
                    threshold="{} modules".format(modules_min),
                    fix={
                        "kind": "increase_quiet_zone",
                        "to": fixed(marginal_limit),
                        "unit": "mm",
                        "from": fixed(margin),
                        "rationale": "clear the marginal band: modules_min x x_dimension x factor",
                    },
                )
            )

    return findings
