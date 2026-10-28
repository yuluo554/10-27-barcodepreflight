"""M5 回读层：纯函数采样器 / 图案表自洽 / `agreement` 三态 / 缺引擎不伪造结论 / 落点。

判据分六组：

  1. **采样器是纯函数**：同输入两次逐字节相等；无随机、无抗锯齿、不读文件（AST + 运行时面）。
  2. **图案表自洽**：L 组奇校验、`G = reverse(complement(L))`、`R = complement(L)`、
     parity 行结构（首位 0 全是 L；1–9 恰好 3 个 G）、96/95 模块总数与守卫。
  3. **栅格化往返**：位图 → 一个**测试侧的小解码器**（只读像素）→ 数字串，必须等于输入；
     这就是"健康样本 oracle 解出"的实测形态（真引擎本机不存在，见第 5 组）。
  4. **DoD 三样本**（`plan/01` §M5 验收）：每模块不足 1 点 → 解不出 + M3 判
     `raster_alias_high_risk`（一致）；健康样本 → 解出 + M3 `pass`（一致）；
     红条 + 红光 → 解不出 + M3 判 `wavelength_reflectance_collapse`（一致）。
  5. **缺引擎不伪造结论**：`oracle_absent`；`agreement` 字段**不产出**；`engine_unusable`
     与 `not-decoded` 分开（否则会凭空产出一条 `m3_laxer` 去"修"不存在的 M3 bug）。
  6. **三态归宿**：`m3_stricter` → `known-disagreements`；`m3_laxer` → bug 通道，
     且 `agreement` 不参与 `verdict`（K25）。

**诚实声明**：本机没有任何候选解码引擎（`data/README.md` §9 第 7 项），所以第 3/4 组的
"解出"是**注入的解码器替身**（它读的是真实落盘的 PNG 像素）——它证明的是**管线**
（采样 → 灰度 → 编码 → 回读 → 归类）通了，**不证明**阈值本身对；阈值对错要真引擎
才能验，而真引擎缺失时本工具只报 `skipped: oracle_absent`。这里**没有**把"没跑"写成"通过"。
"""

import ast
import json
import pathlib
import struct
import zlib

import pytest

from bpreflight import pipeline
from bpreflight import severity as sev
from bpreflight.oracle import agreement, audit, layout, sampler, zxing

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ORACLE_DIR = REPO_ROOT / "src" / "bpreflight" / "oracle"

ELEMENT_STRING = "(01)09501101530003"
DIGITS = "9501101530003"
SYMBOL = "ean13"

#: 灰色分离下限（**测试侧替身**的模型：真实解码器要看见条/空差异）。
_DOUBLE_MIN_GAP = 128


@pytest.fixture(scope="module")
def book():
    from bpreflight import thresholds

    return thresholds.load_book()


@pytest.fixture(scope="module")
def layouts():
    return layout.load()


def _payload(**overrides):
    """健康样本：X=0.330 / DPI=300 / 静区足 / 条高足 / 黑条白底 / 白光。"""
    base = {
        "schema": "bpreflight/spec/1",
        "mode": "params",
        "symbol": SYMBOL,
        "x_dimension_mm": "0.330",
        "target_dpi": 300,
        "quiet_zone_mm": {"left": "4.50", "right": "3.30", "top": "0", "bottom": "0"},
        "bar_height_mm": "22.85",
        "bar_color": "#000000",
        "space_color": "#FFFFFF",
        "illumination": "white",
        "gs1_element_string": ELEMENT_STRING,
    }
    base.update(overrides)
    return base


def _report(payload):
    return pipeline.run(payload, {"file": "spec.json", "sha256": "ab"})


def _ids(report):
    return sorted(f.id for f in report.findings)


def _fake_engine(name="zxing-cpp", version="0.0-test"):
    return zxing.Engine(name, "fake-reader", ("{image}",), version)


# --------------------------------------------------------------------------- #
# 测试侧的小解码器（只读像素；不碰编码侧的模块行）
# --------------------------------------------------------------------------- #


def _read_png(path):
    """Parse our minimal PNG back into `(width, height, line)`.

    Also asserts the two structural promises of the encoder: filter type 0 on every
    scanline, and every scanline identical (a 1-D symbol is one repeated line).
    """
    raw = pathlib.Path(path).read_bytes()
    assert raw.startswith(b"\x89PNG\r\n\x1a\n"), "not a PNG"
    position = 8
    idat = b""
    width = height = None
    while position < len(raw):
        length = struct.unpack(">I", raw[position : position + 4])[0]
        tag = raw[position + 4 : position + 8]
        data = raw[position + 8 : position + 8 + length]
        crc = struct.unpack(">I", raw[position + 8 + length : position + 12 + length])[0]
        assert crc == zlib.crc32(tag + data), "PNG chunk CRC mismatch"
        if tag == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", data[:10])
            assert (depth, colour) == (8, 0), "expected 8-bit grayscale"
        elif tag == b"IDAT":
            idat += data
        position += 12 + length
    pixels = zlib.decompress(idat)
    assert len(pixels) == height * (width + 1), "IDAT size mismatch"
    rows = [pixels[index * (width + 1) : (index + 1) * (width + 1)] for index in range(height)]
    assert all(row[0] == 0 for row in rows), "anti-aliasing filter used"
    assert all(row == rows[0] for row in rows), "1-D raster must be one repeated line"
    return width, height, bytes(rows[0][1:])


def _runs(line):
    out = []
    current = line[0]
    count = 0
    for pixel in line:
        if pixel == current:
            count += 1
        else:
            out.append((current, count))
            current, count = pixel, 1
    out.append((current, count))
    return out


def _digits_of(modules, table, expected):
    """Turn a decoded module row back into digits, then compare with the input."""
    text = "".join("1" if module else "0" for module in modules)
    guards = table.raw["guards"]
    width = table.code_length()
    if not text.startswith(guards["start"]) or not text.endswith(guards["end"]):
        return None
    middle_at = len(guards["start"]) + table.left_digits * width
    if text[middle_at : middle_at + len(guards["middle"])] != guards["middle"]:
        return None
    left = text[len(guards["start"]) : middle_at]
    right = text[middle_at + len(guards["middle"]) : len(text) - len(guards["end"])]

    parity = []
    left_digits = []
    for index in range(table.left_digits):
        group = left[index * width : (index + 1) * width]
        found = None
        for set_name in ("L", "G"):
            for digit, code in enumerate(table.codes[set_name]):
                if group == code:
                    found = (set_name, digit)
        if found is None:
            return None
        parity.append(found[0])
        left_digits.append(str(found[1]))
    leading = [digit for digit, row in table.parity.items() if row == "".join(parity)]
    if len(leading) != 1:
        return None

    right_digits = []
    for index in range(table.right_digits):
        group = right[index * width : (index + 1) * width]
        matches = [str(digit) for digit, code in enumerate(table.codes["R"]) if code == group]
        if len(matches) != 1:
            return None
        right_digits.append(matches[0])

    decoded = leading[0] + "".join(left_digits) + "".join(right_digits)
    return decoded if decoded == expected else None


def _decode_line(line, table, expected, min_gap):
    """A decoder double driven by the *pixels*: returns digits or None."""
    distinct = sorted(set(line))
    space_gray = line[0]
    bars = [gray for gray in distinct if gray != space_gray]
    if len(bars) != 1:
        return None  # no bars, or more than two levels (not our raster)
    bar_gray = bars[0]
    if abs(bar_gray - space_gray) < min_gap:
        return None  # ink and stock look the same to this reader

    runs = _runs(line)
    indices = [index for index, (gray, _) in enumerate(runs) if gray == bar_gray]
    if not indices:
        return None
    field = runs[indices[0] : indices[-1] + 1]
    field_px = sum(count for _, count in field)
    module_px = field_px / float(table.modules_total)

    modules = []
    for gray, count in field:
        units = int(round(count / module_px))
        if units < 1:
            return None  # a module below one device pixel: ratio check cannot hold
        modules.extend([1 if gray == bar_gray else 0] * units)
    if len(modules) != table.modules_total:
        return None
    return _digits_of(modules, table, expected)


def _pixel_runner(layouts, expected=DIGITS, min_gap=_DOUBLE_MIN_GAP):
    """An injectable engine double: it reads the PNG our decoder wrote to disk."""

    def runner(command):
        path = command[-1]
        assert str(path).endswith(".png"), command
        _, _, line = _read_png(path)
        decoded = _decode_line(line, layouts.layout(SYMBOL), expected, min_gap)
        if decoded is None:
            return (4, "", "no barcode found")
        return (0, decoded + "\n", "")

    return runner


def _canned_runner(returncode, out, err=""):
    def runner(command):
        return (returncode, out, err)

    return runner


# --------------------------------------------------------------------------- #
# 1. 采样器是纯函数
# --------------------------------------------------------------------------- #


def test_sampler_is_a_pure_function_of_its_arguments(book, layouts):
    payload = _payload()
    plan = audit._sample_plan(
        payload, _report(payload).encoding_plan, book, layouts,
        book.illumination("white"),
    )
    first = sampler.render(plan["plan"], plan["x_mm"], plan["target_dpi"], "#000000", "#FFFFFF")
    second = sampler.render(plan["plan"], plan["x_mm"], plan["target_dpi"], "#000000", "#FFFFFF")
    assert first.pixels == second.pixels
    assert first.line == second.line
    assert first.min_module_width() == second.min_module_width()

    other = sampler.render(plan["plan"], plan["x_mm"], "203", "#000000", "#FFFFFF")
    assert other.pixels != first.pixels, "DPI 必须真的影响位图，否则判据空跑"


def test_sampler_has_no_randomness_no_antialiasing_and_no_file_access(book, layouts):
    """三条面一起判：AST 无 `random` / 无 `open()`，运行时只有两个灰度级。"""
    source = (ORACLE_DIR / "sampler.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "random" not in imports
    assert not (imports & {"io", "os", "pathlib", "json", "tempfile"}), imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            assert name != "open", "采样器不许读文件"

    payload = _payload()
    report = _report(payload)
    plan = audit._sample_plan(
        payload, report.encoding_plan, book, layouts, book.illumination("white")
    )
    bitmap = sampler.render(plan["plan"], plan["x_mm"], plan["target_dpi"], "#000000", "#FFFFFF")
    assert len(set(bitmap.line)) <= 2, "硬边：只该有条色与空色两种像素，不许抗锯齿"


def test_sampler_refuses_unusable_input(book, layouts):
    payload = _payload()
    plan = audit._sample_plan(
        payload, _report(payload).encoding_plan, book, layouts, book.illumination("white")
    )
    with pytest.raises(sampler.SampleError):
        sampler.render(plan["plan"], "0", "300", "#000000", "#FFFFFF")
    with pytest.raises(sampler.SampleError):
        sampler.render(plan["plan"], "0.330", "300", "metallic", "#FFFFFF")


def test_gray_level_follows_the_illumination_channel():
    """红条在白光下按亮度（33），在红光下按红通道反射率（200）——两项判据的物理基础。"""
    from bpreflight.print.color import parse_color

    red_ink = parse_color("#C8102E")
    assert sampler.gray_level(red_ink, "luminance") == 33
    assert sampler.gray_level(red_ink, "red") == 200
    assert sampler.gray_level(parse_color("#FFFFFF"), "red") == 255
    with pytest.raises(sampler.SampleError):
        sampler.gray_level(red_ink, "ir")


# --------------------------------------------------------------------------- #
# 2. 图案表自洽 + PNG 编码自洽
# --------------------------------------------------------------------------- #


def test_layout_code_sets_are_self_consistent(layouts):
    table = layouts.layout(SYMBOL)
    base = table.codes["L"]
    width = table.code_length()
    for digit, code in enumerate(base):
        assert len(code) == width, digit
        assert code[0] == "0" and code[-1] == "1", code
        assert code.count("1") % 2 == 1, "L 组必须是奇校验（{}）".format(code)
    for digit, code in enumerate(base):
        assert table.codes["R"][digit] == code.translate(str.maketrans("01", "10"))
        assert table.codes["G"][digit] == table.codes["R"][digit][::-1]
        assert table.codes["G"][digit].count("1") % 2 == 0, "G 组必须是偶校验"


def test_layout_parity_rows_cover_every_leading_digit(layouts):
    table = layouts.layout(SYMBOL)
    assert sorted(table.parity) == list("0123456789")
    assert table.parity["0"] == "L" * table.left_digits
    for digit in "123456789":
        row = table.parity[digit]
        assert len(row) == table.left_digits
        assert row.count("G") == 3, "首位 {} 的 parity 行必须恰好 3 个 G（{}）".format(digit, row)


def test_module_row_has_the_documented_structure(layouts):
    table = layouts.layout(SYMBOL)
    row = table.row_for("4006381333931")
    text = "".join("1" if module else "0" for module in row)
    guards = table.raw["guards"]
    assert len(row) == table.modules_total == 95
    assert text.startswith(guards["start"]) and text.endswith(guards["end"])
    assert guards["middle"] in text
    with pytest.raises(layout.LayoutError):
        table.row_for("400638133393")  # 12 位：长度不符，不许产出半条模块行
    with pytest.raises(layout.LayoutError):
        table.row_for("400638133393A")
    with pytest.raises(layout.LayoutError):
        layouts.layout("qr")


def test_png_encoder_is_self_consistent(book, layouts):
    payload = _payload()
    plan = audit._sample_plan(
        payload, _report(payload).encoding_plan, book, layouts, book.illumination("white")
    )
    bitmap = sampler.render(plan["plan"], plan["x_mm"], plan["target_dpi"], "#000000", "#FFFFFF")
    width, height, line = _read_png_bytes(zxing.png_bytes(bitmap))
    assert (width, height) == (bitmap.width, bitmap.height)
    assert line == bitmap.line


def _read_png_bytes(raw):
    """同 `_read_png`，但输入是内存里的字节（不必落盘）。"""
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    position = 8
    idat = b""
    width = height = None
    while position < len(raw):
        length = struct.unpack(">I", raw[position : position + 4])[0]
        tag = raw[position + 4 : position + 8]
        data = raw[position + 8 : position + 8 + length]
        crc = struct.unpack(">I", raw[position + 8 + length : position + 12 + length])[0]
        assert crc == zlib.crc32(tag + data)
        if tag == b"IHDR":
            width, height = struct.unpack(">II", data[:8])
        elif tag == b"IDAT":
            idat += data
        position += 12 + length
    pixels = zlib.decompress(idat)
    assert len(pixels) == height * (width + 1)
    return width, height, bytes(pixels[1 : width + 1])


# --------------------------------------------------------------------------- #
# 3 + 4. DoD 三样本（每模块不足 1 点 / 健康 / 红条 + 红光）
# --------------------------------------------------------------------------- #


def test_healthy_sample_decodes_and_m3_passes(book, layouts):
    payload = _payload()
    report = _report(payload)
    assert report.verdict == "pass" and not report.findings, _ids(report)

    result = audit.assess(report, payload, engine=_fake_engine(), runner=_pixel_runner(layouts))
    doc = result.to_dict()
    assert doc["agreement"] == agreement.CONSISTENT
    assert doc["oracle_result"]["decoded"] is True
    assert doc["oracle_result"]["payload"] == DIGITS
    assert doc["raster"]["modules"] == 95
    assert doc["raster"]["min_module_width"] >= 2
    assert doc["known_disagreements"] == [] and doc["bugs"] == []


def test_under_one_dot_per_module_cannot_be_read_back(book, layouts):
    """`plan/01` §M5 验收：每模块不足 1 点的样本在回读下解不出，且 M3 同判高风险。"""
    payload = _payload(target_dpi=70)
    report = _report(payload)
    assert "raster_alias_high_risk" in _ids(report), _ids(report)

    result = audit.assess(report, payload, engine=_fake_engine(), runner=_pixel_runner(layouts))
    doc = result.to_dict()
    assert doc["oracle_result"]["decoded"] is False
    assert doc["raster"]["min_module_width"] == 0, "低 DPI 下必须有模块退化为 0 像素"
    assert doc["agreement"] == agreement.CONSISTENT
    assert doc["m3_findings"] == ["raster_alias_high_risk"]


def test_red_ink_under_red_light_cannot_be_read_back(book, layouts):
    payload = _payload(bar_color="#C8102E", illumination="red")
    report = _report(payload)
    assert "wavelength_reflectance_collapse" in _ids(report), _ids(report)

    result = audit.assess(report, payload, engine=_fake_engine(), runner=_pixel_runner(layouts))
    doc = result.to_dict()
    assert doc["oracle_result"]["decoded"] is False
    assert doc["agreement"] == agreement.CONSISTENT
    assert doc["m3_findings"] == ["wavelength_reflectance_collapse"]

    # 同一个红条在白光下反而读得出（走亮度项，不跑波长项）——两项判据不合并的直接证据。
    white = _payload(bar_color="#C8102E", illumination="white")
    white_report = _report(white)
    assert not white_report.findings, _ids(white_report)
    white_result = audit.assess(
        white_report, white, engine=_fake_engine(), runner=_pixel_runner(layouts)
    )
    assert white_result.to_dict()["oracle_result"]["decoded"] is True


def test_the_raster_carries_the_spec_quiet_zone(book, layouts):
    """位图按 **spec** 的静区采样，不是按标准最小值：否则"静区被吃掉"在回读层看不见。"""
    payload = _payload(quiet_zone_mm={"left": "0.66", "right": "0.33", "top": "0", "bottom": "0"})
    report = _report(payload)
    plan = audit._sample_plan(
        payload, report.encoding_plan, book, layouts, book.illumination("white")
    )
    bitmap = sampler.render(plan["plan"], plan["x_mm"], plan["target_dpi"], "#000000", "#FFFFFF")
    wide = sampler.render(
        audit._sample_plan(
            _payload(), report.encoding_plan, book, layouts, book.illumination("white")
        )["plan"],
        plan["x_mm"],
        plan["target_dpi"],
        "#000000",
        "#FFFFFF",
    )
    assert bitmap.width < wide.width


# --------------------------------------------------------------------------- #
# 5. 缺引擎 / 引擎不可用：都不许伪造结论
# --------------------------------------------------------------------------- #


def test_oracle_absent_is_declared_and_agreement_is_absent(book, layouts):
    payload = _payload()
    report = _report(payload)
    result = audit.assess(report, payload, engine=None)
    doc = result.to_dict()
    assert doc["skipped"] == [audit.SKIP_ORACLE_ABSENT]
    assert "agreement" not in doc, "缺引擎时不产出 agreement（不是 null —— 是缺席）"
    assert "oracle_result" not in doc and "raster" not in doc
    assert doc["engine"]["name"] == "none"
    assert "oracle_absent" in result.render_md()
    # 主报告一个字都不许变（M5 不参与判定）。
    assert report.verdict == "pass" and not report.findings


def test_probe_without_any_engine_is_none():
    assert zxing.probe(lambda name: None) is None


def test_probe_takes_the_first_declared_candidate():
    def which(name):
        return "/usr/bin/" + name if name == "ZXingReader" else None

    engine = zxing.probe(which)
    assert engine.name == "ZXingReader"
    described = engine.describe()
    assert "path" not in described, "报告不许带可执行文件的绝对路径（§8.7 末条）"
    assert set(described) == {"name", "version", "kind"}


def test_engine_unusable_is_not_read_as_not_decoded(book, layouts):
    """引擎起不来 ≠ 解不出：否则会凭空产出一条 `m3_laxer` 去修不存在的 M3 bug。"""
    payload = _payload()
    report = _report(payload)

    def broken(command):
        raise OSError("no such file")

    result = audit.assess(report, payload, engine=_fake_engine(), runner=broken)
    doc = result.to_dict()
    assert doc["skipped"] and doc["skipped"][0].startswith(audit.SKIP_ENGINE_UNUSABLE)
    assert "agreement" not in doc
    assert doc["bugs"] == [] and doc["known_disagreements"] == []
    # 位图确实采出来了：失败的是引擎，不是采样。
    assert doc["raster"]["width"] > 0


def test_decode_status_contract(book, layouts):
    payload = _payload()
    report = _report(payload)
    plan = audit._sample_plan(
        payload, report.encoding_plan, book, layouts, book.illumination("white")
    )
    bitmap = sampler.render(plan["plan"], plan["x_mm"], plan["target_dpi"], "#000000", "#FFFFFF")

    engine = _fake_engine()
    assert zxing.decode(bitmap, engine, runner=_canned_runner(0, DIGITS + "\n")).status == zxing.DECODED
    assert zxing.decode(bitmap, engine, runner=_canned_runner(0, "\n")).status == zxing.NOT_DECODED
    assert (
        zxing.decode(bitmap, engine, runner=_canned_runner(4, "", "no barcode found")).status
        == zxing.NOT_DECODED
    )
    unusable = zxing.decode(bitmap, engine, runner=_canned_runner(2, "usage: zxing ..."))
    assert unusable.status == zxing.UNUSABLE
    assert not unusable.decoded


# --------------------------------------------------------------------------- #
# 6. 三态归宿 + `agreement` 不进 verdict
# --------------------------------------------------------------------------- #


def test_agreement_is_a_three_value_enum():
    assert set(agreement.AGREEMENTS) == {"consistent", "m3_stricter", "m3_laxer"}
    verdicts = (sev.VERDICT_PASS, sev.VERDICT_WARN, sev.VERDICT_FAIL)
    for verdict in verdicts:
        for decoded in (True, False):
            found, known, bugs = agreement.classify(verdict, decoded, ["x"])
            assert found in agreement.AGREEMENTS
            assert len(known) + len(bugs) == (0 if found == agreement.CONSISTENT else 1)


def test_m3_stricter_goes_to_known_disagreements():
    found, known, bugs = agreement.classify(sev.VERDICT_FAIL, True, ["raster_alias_high_risk"])
    assert found == agreement.M3_STRICTER
    assert bugs == []
    assert known and known[0]["finding_ids"] == ["raster_alias_high_risk"]


def test_m3_laxer_is_a_bug_channel_not_a_known_disagreement():
    found, known, bugs = agreement.classify(sev.VERDICT_PASS, False, [])
    assert found == agreement.M3_LAXER
    assert known == [], "m3_laxer 不许藏进 known-disagreements"
    assert bugs and bugs[0]["agreement"] == agreement.M3_LAXER
    assert "修 M3" in bugs[0]["note"]


def test_not_decoded_with_a_clean_m3_lands_in_the_bug_channel(book, layouts):
    payload = _payload()
    report = _report(payload)
    result = audit.assess(
        report, payload, engine=_fake_engine(), runner=_canned_runner(4, "", "no barcode found")
    )
    doc = result.to_dict()
    assert doc["agreement"] == agreement.M3_LAXER
    assert doc["known_disagreements"] == []
    assert doc["bugs"] and doc["bugs"][0]["m3_verdict"] == "pass"
    assert "BUGS: m3_laxer" in result.render_md()


def test_decoded_while_m3_warns_lands_in_known_disagreements(book, layouts):
    payload = _payload(target_dpi=70)
    report = _report(payload)
    assert report.verdict == "fail", _ids(report)
    result = audit.assess(
        report, payload, engine=_fake_engine(), runner=_canned_runner(0, DIGITS + "\n")
    )
    doc = result.to_dict()
    assert doc["agreement"] == agreement.M3_STRICTER
    assert doc["bugs"] == []
    assert doc["known_disagreements"][0]["finding_ids"] == ["raster_alias_high_risk"]


def test_oracle_never_touches_the_main_verdict(book, layouts):
    """K25：同一 spec 的 verdict/fingerprint 与回读结果无关。"""
    payload = _payload(target_dpi=70)
    report = _report(payload)
    before = (report.verdict, report.fingerprints)

    for runner in (
        _pixel_runner(layouts),
        _canned_runner(0, DIGITS + "\n"),
        _canned_runner(4, "", "no barcode found"),
    ):
        result = audit.assess(report, payload, engine=_fake_engine(), runner=runner)
        doc = result.to_dict()
        assert "verdict" not in doc and "fingerprints" not in doc
        keys = json.loads(result.render_json())
        assert "verdict" not in keys and "fingerprints" not in keys
        assert keys["m3_verdict"] == "fail"
    assert (report.verdict, report.fingerprints) == before


def test_oracle_result_is_deterministic(book, layouts):
    payload = _payload()
    report = _report(payload)
    first = audit.assess(report, payload, engine=_fake_engine(), runner=_pixel_runner(layouts))
    second = audit.assess(report, payload, engine=_fake_engine(), runner=_pixel_runner(layouts))
    assert first.render_json() == second.render_json()
    assert first.render_md() == second.render_md()
    assert first.render_json().endswith("\n") and not first.render_json().endswith("\n\n")


# --------------------------------------------------------------------------- #
# 前提不全 / 不支持：一律 skipped，不许猜
# --------------------------------------------------------------------------- #


def test_unsupported_symbol_is_skipped_with_a_reason():
    payload = {
        "schema": "bpreflight/spec/1",
        "symbol": "qr",
        "x_dimension_mm": "0.330",
        "target_dpi": 300,
        "quiet_zone_mm": {"left": "4", "right": "4", "top": "4", "bottom": "4"},
        "bar_height_mm": "22.85",
        "bar_color": "#000000",
        "space_color": "#FFFFFF",
        "illumination": "white",
    }
    result = audit.assess(_report(payload), payload, engine=_fake_engine())
    doc = result.to_dict()
    assert doc["skipped"] and doc["skipped"][0].startswith(audit.SKIP_SAMPLER_UNSUPPORTED)
    assert "agreement" not in doc


def test_missing_print_fields_are_skipped_with_a_reason():
    payload = {"schema": "bpreflight/spec/1", "symbol": SYMBOL, "target_dpi": 300}
    result = audit.assess(_report(payload), payload, engine=_fake_engine())
    joined = " ".join(result.to_dict()["skipped"])
    assert "sampler_input_incomplete" in joined
    for field in ("x_dimension_mm", "quiet_zone_mm", "bar_height_mm"):
        assert field in joined, joined


def test_unmodelled_illumination_is_skipped_not_guessed():
    payload = _payload(illumination="ir")
    result = audit.assess(_report(payload), payload, engine=_fake_engine())
    doc = result.to_dict()
    assert doc["skipped"] == [
        audit.SKIP_SAMPLER_UNMODELLED_COLOUR + ": illumination ir"
    ]
    assert "agreement" not in doc


def test_engine_with_a_plan_that_has_no_segments_is_skipped():
    payload = _payload()
    report = _report(payload)
    stripped = audit.assess(
        type("R", (object,), {
            "findings": report.findings,
            "input": report.input,
            "encoding_plan": {"segments": []},
        })(),
        payload,
        engine=_fake_engine(),
    )
    assert any(item.startswith(audit.SKIP_SAMPLER_UNENCODABLE_DATA) for item in stripped.to_dict()["skipped"])
    assert "agreement" not in stripped.to_dict()