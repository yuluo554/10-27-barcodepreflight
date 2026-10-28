"""M5 · 回读层编排：前提检查 → 采样 → 外部解码 → `agreement`。

与 M3 的关系（`plan/01` §M5「关键设计」）：

  · **不改 M3 判定**：本模块只**读** `Report` 的派生字段，产出独立的 `oracle` 文档；
  · **缺引擎不产 agreement**：`engine is None` ⇒ 立刻返回 `skipped: oracle_absent`，
    `agreement` 字段**不产出**（不是 null —— 是缺席，`data/README.md` §8.9 G6）；
  · **不伪造结论**：图案表不支持 / 前提不全 / 颜色不可建模 / 引擎驱动不起来，
    一律走 `skipped`，绝不把"没跑"写成"解不出"。把 `engine_unusable` 读成
    `not-decoded` 会凭空产出一条 `m3_laxer` 并逼人去修一个不存在的 M3 bug。

本模块落在**判定层之后**：`pipeline.run` 已经把 findings 与 `encoding_plan` 定稿，
这里不再重算任何判定——`m3_verdict` 只是 M3 findings 的派生投影（`oracle/agreement.py`）。
"""

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from bpreflight import thresholds
from bpreflight.oracle import agreement as agreement_mod
from bpreflight.oracle import layout as layout_mod
from bpreflight.oracle import sampler, zxing

SCHEMA = "bpreflight/oracle-report/1"

#: 不可判通道（都进 `skipped`，都不冒充结论；`data/README.md` §8.9 G6）。
SKIP_ORACLE_ABSENT = "oracle_absent"
SKIP_ENGINE_UNUSABLE = "engine_unusable"
SKIP_SAMPLER_UNSUPPORTED = "sampler_unsupported"
SKIP_SAMPLER_INPUT_INCOMPLETE = "sampler_input_incomplete"
SKIP_SAMPLER_UNMODELLED_COLOUR = "sampler_unmodelled_colour"
SKIP_SAMPLER_UNENCODABLE_DATA = "sampler_unencodable_data"

#: 采样所需的最小输入面（M3 的 `PRINT_FIELDS` 加上条高与颜色 —— 位图需要条高）。
SAMPLE_FIELDS = ("x_dimension_mm", "target_dpi", "quiet_zone_mm", "bar_height_mm")
SAMPLE_COLOUR_FIELDS = ("bar_color", "space_color", "illumination")

#: 定点输出的小数位（K7：出口只出定点字符串）。
THREE_PLACES = Decimal("0.001")

_NOT_GIVEN = object()


class OracleResult(object):
    """一次回读对照的结果（JSON/MD 同源：两个渲染都只读这里的字段）。"""

    __slots__ = (
        "input",
        "engine",
        "m3_verdict",
        "m3_findings",
        "skipped",
        "oracle",
        "agreement",
        "known_disagreements",
        "bugs",
        "raster",
    )

    def __init__(
        self,
        input_info,
        engine,
        m3_verdict,
        m3_findings,
        skipped=None,
        oracle=None,
        agreement=None,
        known_disagreements=None,
        bugs=None,
        raster=None,
    ):
        self.input = dict(input_info or {})
        self.engine = dict(engine or {})
        self.m3_verdict = m3_verdict
        self.m3_findings = tuple(m3_findings or ())
        self.skipped = tuple(skipped or ())
        self.oracle = oracle
        self.agreement = agreement
        self.known_disagreements = tuple(known_disagreements or ())
        self.bugs = tuple(bugs or ())

        self.raster = raster

    def to_dict(self):
        doc = {
            "schema": SCHEMA,
            "input": dict(self.input),
            "engine": dict(self.engine),
            "m3_verdict": self.m3_verdict,
            "m3_findings": list(self.m3_findings),
            "skipped": list(self.skipped),
            "known_disagreements": [dict(item) for item in self.known_disagreements],
            "bugs": [dict(item) for item in self.bugs],
        }
        # `agreement` / `oracle_result` / `raster` 只在**真跑过回读**时出现：
        # 缺引擎时它们必须缺席，而不是 null（`data/README.md` §8.9 G6）。
        if self.oracle is not None:
            doc["oracle_result"] = dict(self.oracle)
        if self.agreement is not None:
            doc["agreement"] = self.agreement
        if self.raster is not None:
            doc["raster"] = dict(self.raster)
        return doc

    def render_json(self):
        text = json.dumps(
            self.to_dict(), sort_keys=True, ensure_ascii=False, indent=2,
            separators=(",", ": "),
        )
        return text + "\n"

    def render_md(self):
        lines = []
        lines.append("ORACLE: {}".format(self.agreement or "skipped"))
        lines.append(
            "ENGINE: {} {}".format(
                self.engine.get("name", "none"),
                self.engine.get("version") or "(version unknown)",
            )
        )
        if self.skipped:
            lines.append("SKIPPED: " + ", ".join(self.skipped))
        lines.append("M3 VERDICT: {}".format(self.m3_verdict or "n/a"))
        lines.append(
            "M3 RISK: " + (", ".join(self.m3_findings) if self.m3_findings else "none")
        )
        if self.oracle is None:
            lines.append("ORACLE RESULT: n/a (this layer did not run)")
        elif self.oracle.get("decoded"):
            lines.append(
                "ORACLE RESULT: decoded=true payload={}".format(self.oracle.get("payload"))
            )
        else:
            lines.append("ORACLE RESULT: decoded=false")
        if self.raster is not None:
            raster = self.raster
            lines.append(
                "RASTER: symbol={} modules={} width={} height={} dots_per_module={} "
                "min_module_width={} sha256={}".format(
                    raster.get("symbol"),
                    raster.get("modules"),
                    raster.get("width"),
                    raster.get("height"),
                    raster.get("dots_per_module"),
                    raster.get("min_module_width"),
                    raster.get("bitmap_sha256"),
                )
            )
        lines.append(_disagreement_line("KNOWN DISAGREEMENTS", self.known_disagreements))
        lines.append(_disagreement_line("BUGS", self.bugs))
        lines.append("")
        return "\n".join(lines)

    def render_md_and_json(self):
        return self.render_md(), self.render_json()


def _disagreement_line(label, entries):
    if not entries:
        return "{}: none".format(label)
    parts = [
        "{} ({}) [{}]".format(
            item.get("agreement"),
            item.get("oracle"),
            ", ".join(item.get("finding_ids") or []) or "no risky finding",
        )
        for item in entries
    ]
    return "{}: {}".format(label, "; ".join(parts))


# --------------------------------------------------------------------------- #
# 编排
# --------------------------------------------------------------------------- #


def assess(report, payload, book=None, layout_book=None, engine=_NOT_GIVEN,
           which=None, runner=None):
    """Read back one spec and compare with M3. Always returns an `OracleResult`.

    `book` / `layout_book` default to the bundled data (loaded here, not inside the
    sampler — `print/` and `oracle/` both receive their data as arguments).
    `engine` / `which` / `runner` are injectable so the agreement logic can be
    exercised with an engine double while the real path stays honest.
    """
    book = book if book is not None else thresholds.load_book()
    layout_book = layout_book if layout_book is not None else layout_mod.load()
    if engine is _NOT_GIVEN:
        engine = zxing.probe(which)

    verdict = agreement_mod.m3_verdict(report.findings)
    risky = agreement_mod.risky_finding_ids(report.findings)
    engine_info = engine.describe() if engine is not None else {
        "name": "none",
        "version": None,
        "kind": "none",
    }

    skipped = []
    if engine is None:
        # 引擎缺失：这一层没跑。不检查也别的前提 —— 报一条就够，不伪造结论。
        skipped.append(SKIP_ORACLE_ABSENT)
        return OracleResult(report.input, engine_info, verdict, risky, skipped=skipped)

    reasons, sample = _preconditions(report, payload, book, layout_book)
    if reasons:
        return OracleResult(
            report.input, engine_info, verdict, risky, skipped=reasons
        )

    try:
        bitmap = sampler.render(
            sample["plan"], sample["x_mm"], sample["target_dpi"],
            payload.get("bar_color"), payload.get("space_color"),
        )
    except sampler.SampleError as exc:
        return OracleResult(
            report.input, engine_info, verdict, risky,
            skipped=[SKIP_SAMPLER_INPUT_INCOMPLETE + ": " + str(exc)],
        )

    outcome = zxing.decode(bitmap, engine, runner=runner)
    if outcome.status == zxing.UNUSABLE:
        return OracleResult(
            report.input, engine_info, verdict, risky,
            skipped=[SKIP_ENGINE_UNUSABLE + ": " + outcome.detail],
            raster=_raster_of(bitmap, sample),
        )

    decoded = outcome.decoded
    agreement, known, bugs = agreement_mod.classify(verdict, decoded, risky)
    oracle = {
        "decoded": decoded,
        "payload": outcome.payload,
        "status": outcome.status,
    }
    if outcome.detail:
        oracle["detail"] = outcome.detail
    return OracleResult(
        report.input,
        engine_info,
        verdict,
        risky,
        oracle=oracle,
        agreement=agreement,
        known_disagreements=known,
        bugs=bugs,
        raster=_raster_of(bitmap, sample),
    )


def _preconditions(report, payload, book, layout_book):
    """Collect every reason this spec cannot be sampled. Empty list = run it."""
    reasons = []
    symbol = payload.get("symbol")
    if symbol is None:
        reasons.append(SKIP_SAMPLER_UNSUPPORTED + ": <no symbol>")
    elif not layout_book.has(symbol):
        # 图案表按符号建模；没建模的符号（2D、别的 1D）不猜图案。
        reasons.append(SKIP_SAMPLER_UNSUPPORTED + ": " + str(symbol))

    plan = report.encoding_plan
    if plan is None:
        reasons.append(SKIP_SAMPLER_UNENCODABLE_DATA + ": " + str(symbol))
    elif not plan.get("segments"):
        reasons.append(SKIP_SAMPLER_UNENCODABLE_DATA + ": " + str(symbol))

    if any(finding.id == "input_incomplete" for finding in report.findings):
        # M3 已经明说"输入不足以判定"：回读层不许在这里产出一个 verdict。
        reasons.append(SKIP_SAMPLER_INPUT_INCOMPLETE + ": input_incomplete")

    missing = [name for name in SAMPLE_FIELDS if payload.get(name) is None]
    if missing:
        reasons.append(
            SKIP_SAMPLER_INPUT_INCOMPLETE + ": " + ",".join(sorted(missing))
        )
    missing_colours = [
        name for name in SAMPLE_COLOUR_FIELDS if payload.get(name) is None
    ]
    if missing_colours:
        reasons.append(
            SKIP_SAMPLER_UNMODELLED_COLOUR + ": " + ",".join(sorted(missing_colours))
        )

    if reasons:
        return reasons, None

    illumination = payload.get("illumination")
    model = book.illumination(illumination)
    if not model.get("modelled"):
        # 未建模的照明（ir 或表外名字）在 M3 是 info: surface_effect_unmodeled；
        # 回读层没有"该通道的灰度"可算，因此也只能不跑（§8.9 G5 / G6）。
        return [SKIP_SAMPLER_UNMODELLED_COLOUR + ": illumination " + str(illumination)], None

    try:
        sample = _sample_plan(payload, plan, book, layout_book, model)
    except sampler.SampleError as exc:
        return [SKIP_SAMPLER_INPUT_INCOMPLETE + ": " + str(exc)], None
    except layout_mod.LayoutError as exc:
        return [SKIP_SAMPLER_UNENCODABLE_DATA + ": " + str(exc)], None
    return [], sample


def _segments_text(plan):
    """The transmitted character stream: segment texts in plan order.

    This is what M2 called `segments[].text` — for a retail symbol the single
    segment is the (zero-padded-stripped) GTIN, i.e. exactly the digits the module
    table encodes.
    """
    return "".join(segment.get("text", "") for segment in plan.get("segments", []))


def _sample_plan(payload, plan, book, layout_book, model):
    symbol = payload.get("symbol")
    layout = layout_book.layout(symbol)
    text = _segments_text(plan)
    row = layout.row_for(text)

    x_mm = sampler.as_decimal(payload.get("x_dimension_mm"), "x_dimension_mm")
    if x_mm <= 0:
        raise sampler.SampleError("x_dimension_mm must be > 0, got {}".format(x_mm))
    target_dpi = sampler.as_decimal(payload.get("target_dpi"), "target_dpi")
    if target_dpi <= 0:
        raise sampler.SampleError("target_dpi must be > 0, got {}".format(target_dpi))

    left_modules, right_modules = _quiet_zone_modules(payload.get("quiet_zone_mm"), x_mm)
    height_mm = sampler.as_decimal(payload.get("bar_height_mm"), "bar_height_mm")
    if height_mm <= 0:
        raise sampler.SampleError("bar_height_mm must be > 0, got {}".format(height_mm))

    plan_out = sampler.SamplePlan(
        symbol=symbol,
        text=text,
        row=row,
        quiet_left_modules=left_modules,
        quiet_right_modules=right_modules,
        height_modules=height_mm / x_mm,
        mm_per_inch=book.mm_per_inch,
        illumination_channel=model.get("channel"),
    )
    return {
        "plan": plan_out,
        "x_mm": x_mm,
        "target_dpi": target_dpi,
    }


def _quiet_zone_modules(raw, x_mm):
    """Quiet-zone module counts per side, exactly as the spec gives them.

    The sampled raster uses the **spec's** quiet zone (not a standard minimum):
    that is what makes "静区被版面吃掉" visible in the read-back layer at all.
    """
    if isinstance(raw, dict):
        left = sampler.as_decimal(raw.get("left", 0), "quiet_zone_mm.left")
        right = sampler.as_decimal(raw.get("right", 0), "quiet_zone_mm.right")
    else:
        left = right = sampler.as_decimal(raw, "quiet_zone_mm")
    return left / x_mm, right / x_mm


def _raster_of(bitmap, sample):
    return {
        "symbol": sample["plan"].symbol,
        "modules": len(sample["plan"].row),
        "width": bitmap.width,
        "height": bitmap.height,
        "dots_per_module": str(
            bitmap.dots_per_module.quantize(THREE_PLACES, rounding=ROUND_HALF_UP)
        ),
        "min_module_width": bitmap.min_module_width(),
        "bitmap_sha256": _bitmap_sha256(bitmap),
    }


def _bitmap_sha256(bitmap):
    """Hash of the sampled raster itself (dims + pixels) — reproducible by hand.

    The PNG bytes are deliberately **not** hashed: zlib output differs between
    Python versions, which would make "same input, same raster" unverifiable.
    """
    digest = hashlib.sha256()
    digest.update("{}\n{}\n".format(bitmap.width, bitmap.height).encode("utf-8"))
    digest.update(bitmap.pixels)
    return digest.hexdigest()