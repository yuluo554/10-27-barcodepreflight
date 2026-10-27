"""C3 · DPI vs dots per module — this tool's own engineering probe (§8.3).

`dots_per_module = x_dimension_mm / mm_per_inch x target_dpi`.

Boundaries (all four tested one by one, §8.3): `< 1.5` -> `raster_alias_high_risk`
(error), `< 2.0` -> `raster_alias_risk` (warn), `>= 2.0` -> ok. So exactly `1.5000`
is a warn (not an error) and exactly `2.0000` is ok.

`basis: "engineering-heuristic"` — this is a rasterisation probe this tool defines,
not a clause of any standard. It therefore has **no** `status` field, its
`threshold_status` is `not-applicable`, and its severity never moves with
`--strict-thresholds` (K8). Mixing it with the gen-spec downgrade would turn
"unverified" into a universal excuse.
"""

from bpreflight import severity as sev
from bpreflight.print.common import (
    as_decimal,
    ceil_decimal,
    engineering_finding,
    fixed,
)

REF = "gen_spec.json#engineering_heuristics.dots_per_module"


def _dpi_text(dpi):
    """Print a DPI as an integer when it is one (`120`, not `1.2E+2`)."""
    if dpi == dpi.to_integral_value():
        return str(int(dpi))
    return str(dpi.normalize())


def check(book, x_dimension_mm, target_dpi, strict_thresholds):
    """Return findings for the raster alias probe (empty when fine).

    `strict_thresholds` is accepted for signature symmetry and deliberately unused:
    an engineering heuristic must not move with it (K8). The unused parameter is the
    visible reminder, not an oversight.
    """
    rule = book.engineering("dots_per_module")
    mm_per_inch = as_decimal(book.mm_per_inch, "mm_per_inch")
    dpi = as_decimal(target_dpi, "target_dpi")

    dots = x_dimension_mm / mm_per_inch * dpi
    error_below = as_decimal(rule["error_below"], "dots_per_module.error_below")
    warn_below = as_decimal(rule["warn_below"], "dots_per_module.warn_below")

    quote = (
        "engineering probe: dots_per_module = x_mm / mm_per_inch * dpi; "
        "< {error} is high risk, < {warn} is a warning".format(
            error=rule["error_below"], warn=rule["warn_below"]
        )
    )

    if dots < error_below:
        finding_id, severity = "raster_alias_high_risk", sev.ERROR
    elif dots < warn_below:
        finding_id, severity = "raster_alias_risk", sev.WARN
    else:
        return []

    # The smallest integer DPI that clears the warn_boundary.
    needed_dpi = ceil_decimal(warn_below * mm_per_inch / x_dimension_mm)
    return [
        engineering_finding(
            finding_id,
            severity,
            observed="{} dots/module ({} mm X at {} dpi)".format(
                fixed(dots), fixed(x_dimension_mm), _dpi_text(dpi)
            ),
            target="raster",
            ref=REF,
            quote=quote,
            threshold=">= {} dots/module".format(rule["warn_below"]),
            fix={
                "kind": "increase_target_dpi",
                "to": str(needed_dpi),
                "unit": "dpi",
                "from": _dpi_text(dpi),
                "min_delta": str(needed_dpi - dpi),
                "rationale": "reach at least {} dots per module so each module spans "
                "multiple device pixels".format(rule["warn_below"]),
            },
        )
    ]
