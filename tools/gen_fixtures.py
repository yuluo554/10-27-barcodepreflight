#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""确定性 fixture 生成器（M3）。

三件东西必须分清（`plan/04` §五、`data/README.md` §7.6）：

  · **生成器**（本文件）入仓；
  · **清单**（`fixtures/manifest.json`）入仓：每件 fixture 的 `sha256` + 生成参数 +
    期望（由本次运行**重算**后落盘，不是人手抄的结论）；
  · **产物**（`fixtures/*.json`）**不入仓**（`.gitignore` 已排除），任何人可重算。

因此"真值"不是某个字节串，而是"输入 + 可由输入独立复算的期望"。本工具每次运行都
把期望算一遍再写进清单；`--check` 则把同样的计算与**已入仓的清单**比对，任何结论漂移
都会变成非零退出。

四条纪律（`plan/04` §五）：

  1. **无网络 / 无随机 / 不读时钟**：只做 `pipeline.run`，不落 `generated_at`；
  2. **`--check` 位级比对**：产物字节与清单 `sha256` 逐件比，0 差异才过；
  3. **部分运行不改写全集清单**：`--suite <name>` 只替换该套件的条目，
     其余条目原样保留（`references/planning-and-data.md` 生成器纪律）；
  4. **空跑即失败**：一个 fixture 都没生成/没比对上时返回非零（判据不许空转）。

用法：
  py -3.12 tools/gen_fixtures.py            # 生成产物 + 写清单
  py -3.12 tools/gen_fixtures.py --check    # 只比对，不写任何文件
  py -3.12 tools/gen_fixtures.py --suite color --check
"""

import argparse
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FIXTURE_DIR = "fixtures"
MANIFEST_PATH = os.path.join(FIXTURE_DIR, "manifest.json")
MANIFEST_SCHEMA = "bpreflight/fixtures/1"

sys.path.insert(0, SRC)

from bpreflight import pipeline  # noqa: E402  (after sys.path so the tool runs uninstalled)
from bpreflight import thresholds  # noqa: E402


def _base(**overrides):
    payload = {
        "schema": "bpreflight/spec/1",
        "mode": "params",
        "symbol": "ean13",
        "x_dimension_mm": "0.330",
        "target_dpi": 203,
        "quiet_zone_mm": {"left": "3.63", "right": "2.31", "top": "0", "bottom": "0"},
        "bar_height_mm": "22.85",
        "bar_color": "#000000",
        "space_color": "#FFFFFF",
        "illumination": "white",
    }
    payload.update(overrides)
    return payload


#: 套装表。`suite` 只用于"部分运行"，不影响产物内容。
FIXTURES = [
    # ---- quiet zone：三档 + 不要求静区的侧 ----
    ("quiet_zone", "qz-healthy", _base()),
    ("quiet_zone", "qz-absent-binaryeye-616", _base(quiet_zone_mm="0")),
    ("quiet_zone", "qz-insufficient-python-barcode-41",
     _base(quiet_zone_mm="0.6", target_dpi=300)),
    ("quiet_zone", "qz-marginal", _base(quiet_zone_mm="3.75", target_dpi=300)),
    ("quiet_zone", "qz-2d-all-sides", _base(symbol="datamatrix", bar_height_mm=None)),

    # ---- raster：四个边界 + §8 三例 ----
    ("raster", "raster-1-4999", _base(target_dpi="1.4999", x_dimension_mm="25.4",
                                      quiet_zone_mm="500", bar_height_mm=None)),
    ("raster", "raster-1-5000", _base(target_dpi="1.5000", x_dimension_mm="25.4",
                                      quiet_zone_mm="500", bar_height_mm=None)),
    ("raster", "raster-1-9999", _base(target_dpi="1.9999", x_dimension_mm="25.4",
                                      quiet_zone_mm="500", bar_height_mm=None)),
    ("raster", "raster-2-0000", _base(target_dpi="2.0000", x_dimension_mm="25.4",
                                      quiet_zone_mm="500", bar_height_mm=None)),
    ("raster", "raster-dpi-100", _base(target_dpi=100)),
    ("raster", "raster-dpi-120", _base(target_dpi=120)),
    ("raster", "raster-dpi-203", _base(target_dpi=203)),

    # ---- magnification：四个边界 ----
    ("magnification", "mag-0-2640-ean13", _base(x_dimension_mm="0.2640", target_dpi=300,
                                                quiet_zone_mm="5", bar_height_mm=None)),
    ("magnification", "mag-0-2639-ean13", _base(x_dimension_mm="0.2639", target_dpi=300,
                                                quiet_zone_mm="5", bar_height_mm=None)),
    ("magnification", "mag-0-6600-ean13", _base(x_dimension_mm="0.6600", target_dpi=300,
                                                quiet_zone_mm="5", bar_height_mm=None)),
    ("magnification", "mag-0-6601-ean13", _base(x_dimension_mm="0.6601", target_dpi=300,
                                                quiet_zone_mm="5", bar_height_mm=None)),

    # ---- bar height ----
    ("bar_height", "bar-height-short", _base(bar_height_mm="10.0", target_dpi=300)),
    ("bar_height", "bar-height-ok", _base(bar_height_mm="22.85")),

    # ---- colour：两项不合并 + 未建模面 ----
    ("color", "color-red-on-white-red-light",
     _base(bar_color="#C8102E", illumination="red", target_dpi=300)),
    ("color", "color-red-on-white-white-light",
     _base(bar_color="#C8102E", illumination="white", target_dpi=300)),
    ("color", "color-grey-insufficient",
     _base(bar_color="#999999", target_dpi=300)),
    ("color", "color-grey-low",
     _base(bar_color="#808080", target_dpi=300)),
    ("color", "color-orange-both-probes",
     _base(bar_color="#C86E00", illumination="red", target_dpi=300)),
    ("color", "color-metallic-unmodelled", _base(bar_color="metallic", target_dpi=300)),
    ("color", "color-infrared-unmodelled", _base(illumination="ir", target_dpi=300)),

    # ---- refusal path ----
    ("refusal", "missing-x-dimension",
     {"schema": "bpreflight/spec/1", "symbol": "ean13", "target_dpi": 300,
      "quiet_zone_mm": "5"}),
    ("refusal", "zero-x-dimension", _base(x_dimension_mm="0")),
    ("refusal", "colour-only",
     {"schema": "bpreflight/spec/1", "bar_color": "#C8102E", "space_color": "#FFFFFF",
      "illumination": "red"}),

    # ---- data layer (M1) + symbols (M2) ----
    ("data_layer", "m1-clean-gtin",
     {"schema": "bpreflight/spec/1", "gs1_element_string": "(01)09501101530003"}),
    ("data_layer", "m1-bad-check-digit",
     {"schema": "bpreflight/spec/1", "identifier": "4006381333932"}),
    ("data_layer", "m2-upca-length",
     {"schema": "bpreflight/spec/1", "symbol": "upca", "identifier": "4006381333931"}),
]

SUITES = sorted({suite for suite, _, _ in FIXTURES})


def _fixture_bytes(payload):
    """The fixture file content: canonical JSON, LF endings, trailing newline."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2)
    return (text + "\n").encode("utf-8")


def _expect(payload):
    """Run the pipeline and record the *recomputed* expectation.

    Storing a verdict here is not "copying a stored truth": it is recomputed on
    every run, and `--check` compares it against the committed manifest — so a
    behaviour change shows up as a diff instead of passing silently.
    """
    report = pipeline.run(payload, {"file": "fixture.json", "sha256": ""})
    return {
        "verdict": report.verdict,
        "findings": sorted(f.id for f in report.findings),
        "skipped": sorted(report.skipped),
    }


def _entry(suite, name, payload):
    raw = _fixture_bytes(payload)
    return {
        "suite": suite,
        "path": "{}/{}.json".format(FIXTURE_DIR, name),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "expect": _expect(payload),
    }


def _load_manifest():
    if not os.path.isfile(MANIFEST_PATH):
        return None
    with io.open(MANIFEST_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _manifest_bytes(fixtures, book):
    doc = {
        "schema": MANIFEST_SCHEMA,
        "generator": "tools/gen_fixtures.py",
        "note": (
            "产物 fixtures/*.json 不入仓（.gitignore）；本清单入仓。"
            "`sha256` 是产物字节的摘要，`expect` 是每次运行重算的期望——"
            "`gen_fixtures.py --check` 用它做位级 + 结论双向比对。"
        ),
        "thresholds_sha256": book.sha256,
        "fixtures": fixtures,
    }
    text = json.dumps(doc, sort_keys=True, ensure_ascii=False, indent=2)
    return (text + "\n").encode("utf-8")


def _write_bytes(rel, raw):
    path = os.path.join(ROOT, rel)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "wb") as handle:
        handle.write(raw)


def generate(suites, keep_existing):
    """Write fixture files + manifest. Returns (written, kept, failures)."""
    book = thresholds.load_book()
    selected = [item for item in FIXTURES if not suites or item[0] in suites]
    if not selected:
        return 0, 0, ["no fixture matched the requested suite(s): {}".format(suites)]

    fixtures = {}
    kept = 0
    if keep_existing:
        existing = _load_manifest() or {}
        for name, entry in (existing.get("fixtures") or {}).items():
            # 部分运行只替换所选套件；其余条目原样保留（含其 expect 与 sha256）。
            if entry.get("suite") not in suites:
                fixtures[name] = entry
                kept += 1

    for suite, name, payload in selected:
        raw = _fixture_bytes(payload)
        _write_bytes("{}/{}.json".format(FIXTURE_DIR, name), raw)
        fixtures[name] = _entry(suite, name, payload)

    _write_bytes(MANIFEST_PATH, _manifest_bytes(fixtures, book))
    return len(selected), kept, []


def check(suites):
    """Compare recomputed fixtures against the committed manifest. Returns failures."""
    manifest = _load_manifest()
    if manifest is None:
        return ["{} is missing; run without --check first".format(MANIFEST_PATH)]

    book = thresholds.load_book()
    if manifest.get("thresholds_sha256") != book.sha256:
        return [
            "threshold vectors changed since the manifest was written "
            "({} != {}); regenerate the manifest in the same commit as the data change".format(
                manifest.get("thresholds_sha256"), book.sha256
            )
        ]

    recorded = manifest.get("fixtures") or {}
    selected = [item for item in FIXTURES if not suites or item[0] in suites]
    if not selected:
        return ["no fixture matched the requested suite(s): {}".format(suites)]

    failures = []
    compared = 0
    for suite, name, payload in selected:
        entry = recorded.get(name)
        if entry is None:
            failures.append("{}: not in the manifest".format(name))
            continue
        compared += 1

        raw = _fixture_bytes(payload)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry.get("sha256"):
            failures.append(
                "{}: fixture bytes differ (manifest {}.. != computed {}..)".format(
                    name, str(entry.get("sha256"))[:12], digest[:12]
                )
            )
            continue

        on_disk = os.path.join(ROOT, entry["path"])
        if os.path.isfile(on_disk):
            with io.open(on_disk, "rb") as handle:
                if handle.read() != raw:
                    failures.append("{}: on-disk fixture is not byte-identical".format(name))

        expected = _expect(payload)
        if expected != entry.get("expect"):
            failures.append(
                "{}: verdict drifted (manifest {!r} != computed {!r})".format(
                    name, entry.get("expect"), expected
                )
            )

    if compared == 0:
        failures.append("0 fixtures compared — the judgement would be empty")

    # 清单里若有本工具已不生成的条目，说明清单过期（部分运行除外）。
    stale = sorted(set(recorded) - {name for _, name, _ in FIXTURES})
    if stale and not suites:
        failures.append("manifest has fixtures the generator no longer produces: {}".format(stale))

    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="gen_fixtures.py",
        description="Deterministic fixture generator (no network, no random, no clock).",
    )
    parser.add_argument("--check", action="store_true",
                        help="compare against the committed manifest; write nothing")
    parser.add_argument("--suite", action="append", choices=SUITES, default=None,
                        help="restrict to one suite (repeatable); other manifest entries are kept")
    args = parser.parse_args(argv)

    out = io.StringIO()
    out.write("fixture 生成器 · 无网络 / 无随机 / 不读时钟\n")
    out.write("=" * 60 + "\n")

    if args.check:
        failures = check(args.suite)
        if failures:
            for failure in failures:
                out.write("FAIL  {}\n".format(failure))
            out.write("=" * 60 + "\n")
            out.write("结论: FAIL（{} 处差异）\n".format(len(failures)))
            sys.stdout.write(out.getvalue())
            return 1
        out.write("PASS  扫描 {} 件 fixture，与清单位级一致，期望无漂移\n".format(
            len([item for item in FIXTURES if not args.suite or item[0] in args.suite])
        ))
        out.write("=" * 60 + "\n")
        out.write("结论: 全绿\n")
        sys.stdout.write(out.getvalue())
        return 0

    written, kept, failures = generate(args.suite, keep_existing=bool(args.suite))
    if failures:
        for failure in failures:
            out.write("FAIL  {}\n".format(failure))
        out.write("=" * 60 + "\n")
        out.write("结论: FAIL\n")
        sys.stdout.write(out.getvalue())
        return 1

    out.write("PASS  写入 {} 件 fixture；清单 {}（保留其它套件 {} 条）\n".format(
        written, MANIFEST_PATH, kept
    ))
    out.write("=" * 60 + "\n")
    out.write("结论: 全绿\n")
    sys.stdout.write(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
