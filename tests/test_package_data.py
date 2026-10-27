"""随包数据：装好的包里必须能读到向量（决策 D15）。

`package-data` 的 glob **不递归**，写成 `data/*` 会漏掉 `data/vectors/`
（`references/release.md` 安装面条）。这条测试是那个坑的常驻防线。
"""

import json

from bpreflight import paths
from bpreflight import thresholds


def test_data_dir_exists():
    import os

    assert os.path.isdir(paths.DATA_DIR), paths.DATA_DIR


def test_vectors_are_readable_and_parse_as_json():
    for name in thresholds.THRESHOLD_FILES:
        doc = paths.load_vector(name)
        assert isinstance(doc, dict), name
        assert doc.get("schema"), name


def test_threshold_book_loads_from_package_data():
    book = thresholds.load_book()
    assert book.sha256
    assert book.quiet_zone["symbols"]
    assert book.gen_spec["values"]


def test_every_gen_spec_item_has_three_state_fields():
    """每个 gen-spec 项必须带 `source` / `status` / `verified_at`（§8.2）。"""
    book = thresholds.load_book()
    scanned = 0
    for symbol in sorted(book.quiet_zone["symbols"]):
        for side in sorted(book.quiet_zone["symbols"][symbol]):
            entry = book.quiet_zone["symbols"][symbol][side]
            for field in ("source", "status", "verified_at", "basis"):
                assert field in entry, "{}.{} misses {}".format(symbol, side, field)
            scanned += 1
    for key in sorted(book.gen_spec["values"]):
        entry = book.gen_spec["values"][key]
        for field in ("source", "status", "verified_at", "basis"):
            assert field in entry, "values.{} misses {}".format(key, field)
        scanned += 1
    assert scanned >= 1


def test_engineering_heuristics_have_no_status_field():
    """工程判据**不参与**未核阈值降级（§8.2 末条）：它们没有 status 字段。"""
    book = thresholds.load_book()
    for key in ("dots_per_module", "contrast_ratio", "wavelength_reflectance_delta_min"):
        entry = book.gen_spec["engineering_heuristics"][key]
        assert "status" not in entry, key
        assert "verified_at" not in entry, key


def test_unverified_keys_are_reported():
    """未核项必须可被枚举（首屏提示与降级都靠它）。"""
    book = thresholds.load_book()
    keys = book.unverified_keys()
    assert keys, "all thresholds verified? then flip a test fixture, not the data"
    assert keys == sorted(keys)


def test_vectors_schema_version_is_pinned():
    for name in thresholds.THRESHOLD_FILES:
        doc = paths.load_vector(name)
        assert doc["schema"].startswith("bpreflight/")
