"""C4 · bar height as a module ratio (`data/README.md` §8.2 / §8.3).

`bar_height_modules = bar_height_mm / x_dimension_mm`, compared against the symbol's
`bar_height_modules_min_<symbol>` gen-spec item. Only the retail linear family has a
placeholder for this today; every other symbol reports nothing rather than borrowing
EAN-13's number (a borrowed number is a fabricated one).

Because the ratio is a `gen-spec` item, an `error` derived from it downgrades to
`warn` while unverified, and `--strict-thresholds` restores it — same rule as C1's
threshold tier and C2.
"""

from bpreflight import severity as sev
from bpreflight.print.common import as_decimal, fixed, gen_spec_finding


def _key(symbol):
    """`bar_height_modules_min_<symbol>` when the data carries one, else None."""
    return "bar_height_modules_min_" + symbol.replace("-", "_")


def check(book, symbol, bar_height_mm, x_dimension_mm, strict_thresholds):
    """Return findings for the bar height ratio (empty when fine or not modelled)."""
    key = _key(symbol)
    if key not in book.gen_spec.get("values", {}):
        # No threshold for this symbol: say nothing rather than reuse another one.
        return []

    entry = book.gen_spec_entry(key)
    modules = bar_height_mm / x_dimension_mm
    modules_min = as_decimal(entry["value"], key)
    if modules >= modules_min:
        return []

    return [
        gen_spec_finding(
            book,
            "bar_height_insufficient",
            sev.ERROR,
            observed="{} modules ({} mm / {} mm X)".format(
                fixed(modules), fixed(bar_height_mm), fixed(x_dimension_mm)
            ),
            target="bar_height",
            entry=entry,
            ref="gen_spec.json#values.{}".format(key),
            strict_thresholds=strict_thresholds,
            threshold=">= {} modules".format(entry["value"]),
            fix={
                "kind": "increase_bar_height",
                "to": fixed(modules_min * x_dimension_mm),
                "unit": "mm",
                "from": fixed(bar_height_mm),
                "rationale": "bar_height_modules_min x x_dimension_mm",
            },
        )
    ]
