"""M5 · 最小采样器（**纯函数**）：`(plan, x_mm, dpi, colors) -> 灰度位图`。

`plan/01` §M5 的两条确定性纪律：

1. **同输入两次调用必须逐字节相等**：无随机、无抗锯齿（硬边）、无时钟、不读文件。
   因此本模块不 `open()` 任何东西——图案表由 `oracle/layout.py` 装载后**以参数传入**，
   与 `print/` 接收 `ThresholdBook` 是同一性质（`plan/HANDOFF-M5` §二.10）。
2. **灰度按固定公式**：sRGB 相对亮度（`data/README.md` §8.4 的公式，系数由
   `print/color.py` 的**唯一定义**给出 —— 采样器不抄第二份），并且**按照明的通道**取值：
   窄带照明（`red`）下要比的是该通道的相对反射率，而不是亮度。这不是细节 ——
   它正是"红条 + 红光在参数域被判塌陷（§8.4）"能在回读域被复现的原因。

几何：`dots_per_module = x_mm / mm_per_inch x dpi`；每个模块边界的像素位置 = 该边界
（以模块为单位）乘以 `dots_per_module` 后**四舍五入**。模块宽度因此可能为 **0 像素**
——这不是缺陷，是低 DPI 下真实存在的失现（"每模块不足 1 点"）。位图里没有任何
抗锯齿：一个像素要么是条色，要么是空色。
"""

from decimal import Decimal, ROUND_HALF_UP

from bpreflight.print.color import channel_reflectance, parse_color, relative_luminance

#: 8-bit 灰度上限（结构常量，不是阈值）。
GRAY_MAX = 255

#: 照明建模表里"按亮度比较"的通道名（`color_cases.json#illuminations.*.channel`）。
LUMINANCE_CHANNEL = "luminance"

BAR = 1
SPACE = 0


class SampleError(ValueError):
    """采样前提不成立（x / dpi / 颜色 / 通道不可用）。调用方落 `skipped`，不产判定。"""


def as_decimal(value, field):
    if isinstance(value, bool) or value is None:
        raise SampleError("{} must be a number, got {!r}".format(field, value))
    try:
        parsed = Decimal(str(value))
    except (ArithmeticError, ValueError):
        raise SampleError("{} is not a number: {!r}".format(field, value))
    if not parsed.is_finite():
        raise SampleError("{} must be finite, got {!r}".format(field, value))
    return parsed


def _round_to_int(value):
    """Half-up rounding to an integer, without touching the decimal context. """
    return int(Decimal(value).to_integral_value(rounding=ROUND_HALF_UP))


def gray_level(rgb, channel):
    """One 8-bit colour -> its grey level under the modelled illumination channel.

    `luminance` uses the WCAG relative-luminance definition; a narrow-band channel
    (`red`) uses that channel's relative reflectance. Both formulas live in
    `print.color` — the sampler deliberately owns no second copy of the sRGB
    constants (`plan/HANDOFF-M5` §二.9).
    """
    if channel == LUMINANCE_CHANNEL:
        value = relative_luminance(rgb)
    elif channel:
        try:
            value = channel_reflectance(rgb, channel)
        except KeyError:
            raise SampleError("unknown illumination channel {!r}".format(channel))
    else:
        raise SampleError("illumination channel is missing; nothing to derive grey from")
    return _round_to_int(value * GRAY_MAX)


class SamplePlan(object):
    """Everything the rasteriser needs, all of it already decided upstream.

    Deliberately not a data file and not a `Report`: the sampling plan is the
    *rendering* contract (module row + quiet zone + height + unit constant +
    illumination channel), so `render()` stays a pure function of its arguments.
    """

    __slots__ = (
        "symbol",
        "text",
        "row",
        "quiet_left_modules",
        "quiet_right_modules",
        "height_modules",
        "mm_per_inch",
        "illumination_channel",
    )

    def __init__(
        self,
        symbol,
        text,
        row,
        quiet_left_modules,
        quiet_right_modules,
        height_modules,
        mm_per_inch,
        illumination_channel,
    ):
        self.symbol = symbol
        self.text = text
        self.row = list(row)
        self.quiet_left_modules = Decimal(quiet_left_modules)
        self.quiet_right_modules = Decimal(quiet_right_modules)
        self.height_modules = Decimal(height_modules)
        self.mm_per_inch = Decimal(mm_per_inch)
        self.illumination_channel = illumination_channel


class Bitmap(object):
    """A 1-D raster: one grey scanline repeated `height` times (no anti-aliasing)."""

    __slots__ = (
        "width",
        "height",
        "line",
        "bar_gray",
        "space_gray",
        "dots_per_module",
        "module_widths",
    )

    def __init__(self, width, height, line, bar_gray, space_gray, dots_per_module,
                 module_widths):
        self.width = width
        self.height = height
        self.line = bytes(line)
        self.bar_gray = bar_gray
        self.space_gray = space_gray
        self.dots_per_module = dots_per_module
        self.module_widths = tuple(module_widths)

    @property
    def pixels(self):
        """The full pixel buffer (same scanline repeated)."""
        return self.line * self.height

    def min_module_width(self):
        """The narrowest module in device pixels — `0` means that module vanished.

        This is the quantity a real renderer loses first when the target DPI is too
        low for the X-dimension, and it is what makes the "under one dot per module"
        sample fail to decode (`plan/01` §M5 验收).
        """
        return min(self.module_widths)


def _px(modules, dots_per_module):
    """Pixel position of a module boundary (half-up, exact decimal arithmetic)."""
    return _round_to_int(Decimal(modules) * dots_per_module)


def render(plan, x_mm, dpi, bar_color, space_color):
    """Sample one grayscale bitmap. Pure: same arguments -> byte-identical result.

    `plan` is a `SamplePlan`; `x_mm` / `dpi` are the M3 print parameters (Decimal,
    string or int — anything `Decimal()` accepts); `bar_color` / `space_color` are
    `#RRGGBB` strings. Anything unusable raises `SampleError` instead of guessing.
    """
    x = as_decimal(x_mm, "x_dimension_mm")
    if x <= 0:
        raise SampleError("x_dimension_mm must be > 0, got {}".format(x))
    target_dpi = as_decimal(dpi, "target_dpi")
    if target_dpi <= 0:
        raise SampleError("target_dpi must be > 0, got {}".format(target_dpi))

    dots_per_module = x / plan.mm_per_inch * target_dpi

    bar_rgb = parse_color(bar_color)
    space_rgb = parse_color(space_color)
    if bar_rgb is None or space_rgb is None:
        raise SampleError(
            "bar/space colour must be an 8-bit #RRGGBB value (got {!r} / {!r})".format(
                bar_color, space_color
            )
        )
    bar_gray = gray_level(bar_rgb, plan.illumination_channel)
    space_gray = gray_level(space_rgb, plan.illumination_channel)

    # Boundaries are computed over the whole line (quiet zone + modules + quiet
    # zone), so a fractional quiet zone is preserved exactly as the spec gives it.
    left = plan.quiet_left_modules
    boundaries = [_px(left + index, dots_per_module) for index in range(len(plan.row) + 1)]
    width = _px(left + len(plan.row) + plan.quiet_right_modules, dots_per_module)
    if width <= 0:
        raise SampleError(
            "the sampled raster has zero width ({} modules at {} dots/module)".format(
                left + len(plan.row) + plan.quiet_right_modules, dots_per_module
            )
        )
    height = max(_px(plan.height_modules, dots_per_module), 1)

    line = bytearray([space_gray] * width)
    widths = []
    for index, module in enumerate(plan.row):
        start, end = boundaries[index], boundaries[index + 1]
        widths.append(end - start)
        if module == BAR:
            for pixel in range(max(start, 0), min(end, width)):
                line[pixel] = bar_gray

    return Bitmap(
        width=width,
        height=height,
        line=line,
        bar_gray=bar_gray,
        space_gray=space_gray,
        dots_per_module=dots_per_module,
        module_widths=widths,
    )