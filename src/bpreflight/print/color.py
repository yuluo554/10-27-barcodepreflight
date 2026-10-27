"""C5 · bar/space colour comparability — two criteria that must never be merged.

`data/README.md` §8.4 defines exactly two probes:

1. **Luminance contrast** — `contrast_ratio = (L_light + k) / (L_dark + k)` with `L`
   the sRGB relative luminance of each 8-bit colour. `< 3.0` -> `insufficient_contrast`
   (error), `< 4.5` -> `low_contrast` (warn).
2. **Wavelength channel** — under a narrow-band illumination (red), the bar and the
   space must differ enough in *that channel's* reflectance. Too small a difference
   -> `wavelength_reflectance_collapse` (error).

Why they are separate ids, never merged: the canonical misjudgement in this area is
"red ink under red light = low contrast". It is not low contrast — `#C8102E` on white
is 5.88:1 under **white** light (perfectly readable) and *invisible* under **red**
light because both the red ink and the white stock reflect the red channel almost
equally. Reported as one merged item, that nuance dies. Both stay separate and neither
suppresses the other.

`basis: "engineering-heuristic"` for both (K8): no `status`, no downgrade, severity
constant. The illumination table (`color_cases.json`) says which illuminations are
modelled at all; anything outside it becomes `info: surface_effect_unmodeled`
(§8.9 G5) — never a pass and never a fail.
"""

from decimal import Decimal

from bpreflight import severity as sev
from bpreflight.print.common import as_decimal, engineering_finding, fixed

REF_LUMINANCE = "gen_spec.json#engineering_heuristics.contrast_ratio"
REF_WAVELENGTH = "gen_spec.json#engineering_heuristics.wavelength_reflectance_delta_min"
REF_ILLUMINATION = "color_cases.json#illuminations.{}"

#: sRGB / WCAG constants. These are the *definition* of relative luminance, not
#: thresholds: changing a calibration value changes these, changing a policy
#: threshold does not (`tools/check_thresholds.py` draws the same line).
_GAMMA_OFFSET = Decimal("0.055")
_GAMMA_DIVISOR = Decimal("1.055")
_GAMMA_EXPONENT = Decimal("2.4")
_LINEAR_CUTOFF = Decimal("0.03928")
_LINEAR_DIVISOR = Decimal("12.92")
_WEIGHTS = (Decimal("0.2126"), Decimal("0.7152"), Decimal("0.0722"))
_CHANNEL_MAX = Decimal(255)

_CHANNEL_INDEX = {"red": 0, "green": 1, "blue": 2}

#: An sRGB hex colour is `#` + one byte per channel (structure, not a threshold).
_CHANNEL_COUNT = len(_WEIGHTS)


def parse_color(raw):
    """`#RRGGBB` -> (r, g, b) ints. Anything else is 'unmodelled', not an error."""
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text.startswith("#"):
        return None
    try:
        octets = bytes.fromhex(text[1:])
    except ValueError:
        return None
    if len(octets) != _CHANNEL_COUNT:
        return None
    return tuple(octets)


def _linearise(channel):
    value = Decimal(channel) / _CHANNEL_MAX
    if value <= _LINEAR_CUTOFF:
        return value / _LINEAR_DIVISOR
    return ((value + _GAMMA_OFFSET) / _GAMMA_DIVISOR) ** _GAMMA_EXPONENT


def relative_luminance(rgb):
    """sRGB relative luminance of an 8-bit triple (WCAG definition)."""
    r, g, b = (_linearise(channel) for channel in rgb)
    return _WEIGHTS[0] * r + _WEIGHTS[1] * g + _WEIGHTS[2] * b


def contrast_ratio(first, second):
    """`(L_light + k) / (L_dark + k)` with `k = 0.05` from the WCAG formula."""
    light, dark = relative_luminance(first), relative_luminance(second)
    if light < dark:
        light, dark = dark, light
    return (light + Decimal("0.05")) / (dark + Decimal("0.05"))


def channel_reflectance(rgb, channel):
    """Relative reflectance in one channel (0..1). Simple ratio, no ICC profile.

    No colour management is performed on purpose (`plan/00`: no lcms, no ICC) — the
    probe compares the same physical channel on both sides, which is all the
    "reflectance collapse" argument needs.
    """
    return Decimal(rgb[_CHANNEL_INDEX[channel]]) / _CHANNEL_MAX


def _unmodelled(reason, target):
    return engineering_finding(
        "surface_effect_unmodeled",
        sev.INFO,
        observed=reason,
        target=target,
        ref="color_cases.json",
        quote="materials / illuminations outside the two modelled probes get an info, "
        "never a pass and never a fail (data/README.md 8.9 G5)",
    )


def check(book, bar_color, space_color, illumination):
    """Return the colour findings for one spec (possibly several, possibly none)."""
    bar_rgb = parse_color(bar_color)
    space_rgb = parse_color(space_color)
    if bar_rgb is None or space_rgb is None:
        bad = "bar_color" if bar_rgb is None else "space_color"
        return [
            _unmodelled(
                "{} {!r} is not an 8-bit #RRGGBB value; ink reflectance is not modelled".format(
                    bad, bar_color if bar_rgb is None else space_color
                ),
                "color",
            )
        ]

    model = book.illumination(illumination)
    if not model.get("modelled"):
        return [
            _unmodelled(
                "illumination {!r} is outside the modelled probes ({}); ink reflectance "
                "cannot be derived from sRGB".format(
                    illumination, model.get("note", "unmodelled")
                ),
                "color",
            )
        ]

    findings = []

    # Probe 1: luminance contrast (always, for a modelled illumination).
    rule = book.engineering("contrast_ratio")
    ratio = contrast_ratio(bar_rgb, space_rgb)
    error_below = as_decimal(rule["error_below"], "contrast_ratio.error_below")
    warn_below = as_decimal(rule["warn_below"], "contrast_ratio.warn_below")
    if ratio < error_below:
        findings.append(
            engineering_finding(
                "insufficient_contrast",
                sev.ERROR,
                observed="{}:1 ({} on {})".format(fixed(ratio), bar_color, space_color),
                target="color.luminance",
                ref=REF_LUMINANCE,
                quote="contrast_ratio = (L_light + .05) / (L_dark + .05), sRGB relative luminance",
                threshold=">= {}:1".format(rule["warn_below"]),
                fix={
                    "kind": "increase_luminance_contrast",
                    "min_delta": fixed(warn_below - ratio),
                    "unit": "contrast-ratio",
                    "rationale": "darken the bars or lighten the space to reach {}:1".format(
                        rule["warn_below"]
                    ),
                },
            )
        )
    elif ratio < warn_below:
        findings.append(
            engineering_finding(
                "low_contrast",
                sev.WARN,
                observed="{}:1 ({} on {})".format(fixed(ratio), bar_color, space_color),
                target="color.luminance",
                ref=REF_LUMINANCE,
                quote="contrast_ratio = (L_light + .05) / (L_dark + .05), sRGB relative luminance",
                threshold=">= {}:1".format(rule["warn_below"]),
                fix={
                    "kind": "increase_luminance_contrast",
                    "min_delta": fixed(warn_below - ratio),
                    "unit": "contrast-ratio",
                    "rationale": "reach {}:1 to leave the marginal band".format(
                        rule["warn_below"]
                    ),
                },
            )
        )

    # Probe 2: narrow-band reflectance collapse (only where a channel is modelled
    # and it is not plain luminance). Never merged with probe 1.
    channel = model.get("channel")
    if channel in _CHANNEL_INDEX:
        delta_rule = book.engineering("wavelength_reflectance_delta_min")
        delta_min = as_decimal(delta_rule["value"], "wavelength_reflectance_delta_min")
        bar_reflectance = channel_reflectance(bar_rgb, channel)
        space_reflectance = channel_reflectance(space_rgb, channel)
        delta = abs(space_reflectance - bar_reflectance)
        if delta < delta_min:
            needed = space_reflectance - delta_min
            findings.append(
                engineering_finding(
                    "wavelength_reflectance_collapse",
                    sev.ERROR,
                    observed="{} {}-channel reflectance difference (bar {}, space {})".format(
                        fixed(delta), channel, fixed(bar_reflectance), fixed(space_reflectance)
                    ),
                    target="color.wavelength",
                    ref=REF_WAVELENGTH,
                    quote=model.get("source", ""),
                    threshold=">= {} relative reflectance".format(delta_rule["value"]),
                    fix={
                        "kind": "choose_ink_with_channel_contrast",
                        "to": "< {} in the {} channel".format(
                            fixed(needed) if needed > 0 else "0.000", channel
                        ),
                        "unit": "relative-reflectance",
                        "rationale": "under {} light the two sides must differ in that "
                        "channel; a colour shift or a different illumination is required".format(
                            channel
                        ),
                    },
                )
            )

    return findings
