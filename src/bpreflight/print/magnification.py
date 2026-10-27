"""C2 · X-dimension vs magnification (`data/README.md` §8.3).

`magnification_pct = x_dimension_mm / nominal_x_mm x 100`; below the range floor or
above the ceiling is a `warn`. Boundary semantics are inclusive on the inside:
exactly `0.2640` (= 80 %) and exactly `0.6600` (= 200 %) are *not* reported; one
unit below/above (at fixed precision) is.

Both the range and the nominal X are `gen-spec` items, so the `warn` here is a
plain `warn` either way — but the threshold status still has to travel with the
finding so the report can say "this came from an unverified range".
"""

from bpreflight import severity as sev
from bpreflight.print.common import as_decimal, engineering_finding, fixed, gen_spec_finding

REF_NOMINAL = "gen_spec.json#values.nominal_x_mm"
REF_MIN = "gen_spec.json#values.magnification_min_pct"
REF_MAX = "gen_spec.json#values.magnification_max_pct"

#: Percent basis (structural: it is how "per cent" is defined, not a threshold).
PERCENT = 100


def check(book, x_dimension_mm, strict_thresholds):
    """Return findings for the magnification range (empty when inside)."""
    nominal = as_decimal(book.gen_spec_entry("nominal_x_mm")["value"], "nominal_x_mm")
    min_entry = book.gen_spec_entry("magnification_min_pct")
    max_entry = book.gen_spec_entry("magnification_max_pct")

    percent = x_dimension_mm / nominal * PERCENT
    findings = []

    if percent < as_decimal(min_entry["value"], "magnification_min_pct"):
        findings.append(
            gen_spec_finding(
                book,
                "magnification_below_range",
                sev.WARN,
                observed="{}% ({} mm / {} mm)".format(
                    fixed(percent), fixed(x_dimension_mm), fixed(nominal)
                ),
                target="magnification",
                entry=min_entry,
                ref=REF_MIN,
                strict_thresholds=strict_thresholds,
                threshold=">= {}%".format(min_entry["value"]),
                fix={
                    "kind": "increase_x_dimension",
                    "to": fixed(nominal * as_decimal(min_entry["value"], "min") / PERCENT),
                    "unit": "mm",
                    "from": fixed(x_dimension_mm),
                    "rationale": "reach the bottom of the accepted magnification range",
                },
            )
        )
    elif percent > as_decimal(max_entry["value"], "magnification_max_pct"):
        findings.append(
            gen_spec_finding(
                book,
                "magnification_above_range",
                sev.WARN,
                observed="{}% ({} mm / {} mm)".format(
                    fixed(percent), fixed(x_dimension_mm), fixed(nominal)
                ),
                target="magnification",
                entry=max_entry,
                ref=REF_MAX,
                strict_thresholds=strict_thresholds,
                threshold="<= {}%".format(max_entry["value"]),
                fix={
                    "kind": "decrease_x_dimension",
                    "to": fixed(nominal * as_decimal(max_entry["value"], "max") / PERCENT),
                    "unit": "mm",
                    "from": fixed(x_dimension_mm),
                    "rationale": "stay within the accepted magnification range",
                },
            )
        )

    return findings
