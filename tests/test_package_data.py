"""随包数据：装好的包里必须能读到向量与内嵌字典（决策 D15）。

`package-data` 的 glob **不递归**，写成 `data/*` 会漏掉 `data/vectors/`
（`references/release.md` 安装面条）。这条测试是那个坑的常驻防线。
M1 又加了一层：`data/gs1-syntax-dictionary/` 是**目录**，glob 同样不递归。
"""

import json
import os

import pytest

from bpreflight import canonical
from bpreflight import paths
from bpreflight import thresholds
from bpreflight.gs1 import dictionary, vectors


def test_data_dir_exists():
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


def test_every_shipped_vector_file_is_declared_and_readable():
    """`THRESHOLD_FILES` 只管阈值；包内还有 gs1 向量与字典清单，必须都能读到。"""
    for name in paths.VECTOR_FILES:
        path = paths.vector_path(name)
        assert os.path.isfile(path), "{} 不在包里（package-data 漏了？）".format(name)
        if name.endswith(".json"):
            with open(path, "r", encoding="utf-8") as handle:
                assert json.load(handle), name


# --------------------------------------------------------------------------- #
# M1 内嵌官方字典
# --------------------------------------------------------------------------- #


def test_dictionary_text_is_shipped():
    """字典正文必须随包（`package-data` 的 glob 不递归到子目录）。"""
    manifest = dictionary.load_manifest()
    path = dictionary.dictionary_path(manifest)
    assert os.path.isfile(path), "字典正文不在包里: {}".format(manifest["path"])


def test_dictionary_license_and_notice_are_shipped():
    """Apache-2.0 的归属要求：上游许可与来源声明必须与正文同包。"""
    for name in ("LICENSE", "NOTICE"):
        path = os.path.join(paths.DICT_DIR, name)
        assert os.path.isfile(path), "{} 缺失（许可归属要求）".format(path)
    notice = open(os.path.join(paths.DICT_DIR, "NOTICE"), encoding="utf-8").read()
    for token in ("Apache", "gs1/gs1-syntax-dictionary", "2026-10-27"):
        assert token in notice, "NOTICE 缺 {!r}（上游许可 / 来源 URL / 快照日期）".format(token)


def test_dictionary_loads_from_package_data():
    doc = dictionary.load()
    assert len(doc) > 0
    assert doc.dict_version
    assert doc.sha256


def test_gs1_vectors_load_from_package_data():
    doc = vectors.load()
    assert doc["checksum"]["vectors"]
    assert vectors.load_century_resolution()
    assert vectors.identifier_lengths()


def test_altered_dictionary_is_refused(tmp_path):
    """摘要不符 = 安装损坏 → 报错，而不是拿改过的表继续判（`plan/00` 台账行）。"""
    manifest = dict(dictionary.load_manifest())
    manifest["sha256"] = "0" * 64
    with pytest.raises(dictionary.DictionaryError) as excinfo:
        dictionary.load(manifest)
    assert "digest mismatch" in str(excinfo.value)


def test_missing_dictionary_is_refused(tmp_path):
    manifest = dict(dictionary.load_manifest())
    manifest["path"] = "gs1-syntax-dictionary/does-not-exist.txt"
    with pytest.raises(dictionary.DictionaryError):
        dictionary.load(manifest)


# --------------------------------------------------------------------------- #
# M6 行尾归一（`data/README.md` §8.11）
# --------------------------------------------------------------------------- #


def test_canonical_digest_ignores_line_endings(tmp_path):
    """同一份内容的 LF 与 CRLF 副本必须算出同一个摘要（换平台克隆不能换摘要）。"""
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "a": 1\n}\n')
    crlf.write_bytes(b'{\r\n  "a": 1\r\n}\r\n')
    assert canonical.sha256_of_bytes(lf.read_bytes()) == canonical.sha256_of_bytes(
        crlf.read_bytes()
    )
    assert canonical.read_normalized(str(lf))[1] == canonical.read_normalized(str(crlf))[1]


def test_crlf_copy_of_the_dictionary_still_verifies():
    """内嵌字典转成 CRLF 后，摘要仍须等于 `dict_manifest.json` 里的值。

    M6 实测形态：`git archive`（受 `core.autocrlf` 影响）导出 CRLF → 打包 → 装好后
    `dictionary.load()` 抛 `DictionaryError`。这条测试把那个场景钉在单测里。
    """
    manifest = dictionary.load_manifest()
    with open(dictionary.dictionary_path(manifest), "rb") as handle:
        raw = handle.read()
    crlf = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    assert b"\r\n" in crlf, "字典正文里没有换行？这条测试的构造前提失效了"
    assert canonical.sha256_of_bytes(crlf) == manifest["sha256"]


def test_canonical_digest_still_changes_when_content_changes():
    """归一是"忽略行尾"，不是"什么变化都放行"（阳性对照）。"""
    assert canonical.sha256_of_bytes(b"a\nb\n") != canonical.sha256_of_bytes(b"a\nc\n")
