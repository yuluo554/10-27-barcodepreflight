"""fixture 生成器纪律：确定性、位级自检、部分运行不改写全集清单。

`tools/gen_fixtures.py` 的关键不是"能生成文件"，而是三条可跑红的性质
（`plan/04` §五）：

  1. **确定性**：同一输入重跑，产物字节与清单 `sha256` 完全一致；
  2. **`--check` 位级比对**：篡改清单里任一 `sha256` / `expect` / 阈值身份 →
     必须报差异（脚本据此非零退出）；
  3. **部分运行不改写全集**：`--suite color` 之后，其它套件的条目原样保留。

**为什么用 monkeypatch 而不是"复制仓库再改文件"**：这些判据都是纯函数
（`check()` / `generate()`）的逻辑，用文件系统去驱动它们只会让测试变成"我能写
临时目录吗"。这里把 `_load_manifest` / `_write_bytes` 换成记录器：判据跑的是真代码，
但一个字节都不落盘，也就不存在"测试自己成了路径面"的问题。

真进程只跑两件**只读**的事：`--check` 在真仓库上必须全绿；未知 `--suite` 必须被拒。
"""

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from tools import gen_fixtures  # noqa: E402  (path inserted above)

MANIFEST = os.path.join(REPO_ROOT, "fixtures", "manifest.json")


def _committed_manifest():
    with open(MANIFEST, encoding="utf-8") as handle:
        return json.load(handle)


class _Recorder(object):
    """Stand-in for the generator's disk writers: remembers instead of writing."""

    def __init__(self):
        self.written = {}

    def write(self, rel, raw):
        self.written[rel] = raw

    def manifest(self):
        raw = self.written.get(gen_fixtures.MANIFEST_PATH)
        return json.loads(raw.decode("utf-8")) if raw else None


@pytest.fixture
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(gen_fixtures, "_write_bytes", rec.write)
    return rec


# --------------------------------------------------------------------------- #
# 1. 入仓纪律 / 真实树的只读自检
# --------------------------------------------------------------------------- #


def test_manifest_is_committed_and_fixtures_are_not():
    """入仓的是清单；产物不入仓（`.gitignore` 里逐条放过 manifest）。"""
    assert os.path.isfile(MANIFEST)
    with open(os.path.join(REPO_ROOT, ".gitignore"), encoding="utf-8") as handle:
        text = handle.read()
    assert "fixtures/*.json" in text
    assert "!fixtures/manifest.json" in text


def test_check_passes_on_the_current_tree():
    proc = subprocess.run(
        [sys.executable, "-X", "utf8",
         os.path.join(REPO_ROOT, "tools", "gen_fixtures.py"), "--check"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, output
    assert "全绿" in output


def test_manifest_thresholds_identity_matches_the_book():
    """阈值册一改，清单必须同提交重生成（这条把两者钉在一起）。"""
    from bpreflight import thresholds

    assert _committed_manifest()["thresholds_sha256"] == thresholds.load_book().sha256


def test_every_suite_is_represented():
    suites = {entry["suite"] for entry in _committed_manifest()["fixtures"].values()}
    assert {
        "quiet_zone", "raster", "magnification", "bar_height", "color",
        "refusal", "data_layer",
    } <= suites


def test_every_manifest_entry_points_at_its_own_fixture():
    """清单条目的 `path` 与键名必须自洽（改名字漏改路径会让产物与清单脱钩）。"""
    for name, entry in _committed_manifest()["fixtures"].items():
        assert entry["path"] == "fixtures/{}.json".format(name), name
        assert entry["sha256"] and entry["expect"]["verdict"] in ("pass", "warn", "fail")


def test_generator_is_deterministic(recorder):
    """同一输入跑两次，产物与清单字节完全一致（无随机、无时钟）。"""
    first, _, failures = gen_fixtures.generate(None, keep_existing=False)
    assert failures == []
    snapshot = dict(recorder.written)

    recorder.written.clear()
    second, _, failures = gen_fixtures.generate(None, keep_existing=False)
    assert failures == []
    assert first == second == len(gen_fixtures.FIXTURES)
    assert recorder.written == snapshot


# --------------------------------------------------------------------------- #
# 2. `check()` 的每条比对都真的咬得住（篡改内存里的清单，不碰磁盘）
# --------------------------------------------------------------------------- #


def _patched_manifest(monkeypatch, mutate):
    doc = _committed_manifest()
    mutate(doc)
    monkeypatch.setattr(gen_fixtures, "_load_manifest", lambda: doc)
    return doc


def test_check_is_clean_against_the_committed_manifest(monkeypatch):
    assert gen_fixtures.check(None) == []


def test_tampered_sha_is_caught(monkeypatch):
    def mutate(doc):
        name = sorted(doc["fixtures"])[0]
        doc["fixtures"][name]["sha256"] = "0" * 64

    _patched_manifest(monkeypatch, mutate)
    failures = gen_fixtures.check(None)
    assert failures
    assert "bytes differ" in " ".join(failures)


def test_drifted_expectation_is_caught(monkeypatch):
    """期望漂移（判定行为变了）也必须被抓——不只是字节。"""
    def mutate(doc):
        name = sorted(doc["fixtures"])[0]
        doc["fixtures"][name]["expect"]["verdict"] = (
            "fail" if doc["fixtures"][name]["expect"]["verdict"] != "fail" else "pass"
        )

    _patched_manifest(monkeypatch, mutate)
    failures = gen_fixtures.check(None)
    assert failures
    assert "drifted" in " ".join(failures)


def test_tampered_thresholds_identity_is_caught(monkeypatch):
    def mutate(doc):
        doc["thresholds_sha256"] = "0" * 64

    _patched_manifest(monkeypatch, mutate)
    failures = gen_fixtures.check(None)
    assert failures
    assert "regenerate" in " ".join(failures)


def test_missing_entry_is_caught(monkeypatch):
    def mutate(doc):
        del doc["fixtures"][sorted(doc["fixtures"])[0]]

    _patched_manifest(monkeypatch, mutate)
    failures = gen_fixtures.check(None)
    assert failures
    assert "not in the manifest" in " ".join(failures)


def test_stale_entry_is_caught(monkeypatch):
    """清单里有生成器不再产出的条目 = 清单过期，必须红。"""
    def mutate(doc):
        doc["fixtures"]["ghost-fixture"] = dict(doc["fixtures"][sorted(doc["fixtures"])[0]])

    _patched_manifest(monkeypatch, mutate)
    failures = gen_fixtures.check(None)
    assert failures
    assert "no longer produces" in " ".join(failures)


# --------------------------------------------------------------------------- #
# 3. 部分运行：不改写全集清单
# --------------------------------------------------------------------------- #


def test_partial_run_keeps_other_suites(recorder, monkeypatch):
    """`--suite color` 只替换 color 条目；其余条目原样保留。

    判据不只看条数：把某条**非 color** 条目的 sha256 改成一个假值交给生成器，
    部分运行写出的新清单里它必须**原样还在**（说明没被"重跑全集"覆盖）。
    """
    doc = _committed_manifest()
    others = {
        name: entry for name, entry in doc["fixtures"].items()
        if entry["suite"] != "color"
    }
    assert others, "清单里没有非 color 条目 —— 这条测试会空跑"
    sentinel = sorted(others)[0]
    doc["fixtures"][sentinel]["sha256"] = "f" * 64
    monkeypatch.setattr(gen_fixtures, "_load_manifest", lambda: doc)

    written, kept, failures = gen_fixtures.generate(["color"], keep_existing=True)
    assert failures == []
    assert kept == len(others)

    after = recorder.manifest()
    assert after["fixtures"][sentinel]["sha256"] == "f" * 64, (
        "部分运行覆盖了不属于该套件的条目"
    )
    color_before = {n for n, e in doc["fixtures"].items() if e["suite"] == "color"}
    color_after = {n for n, e in after["fixtures"].items() if e["suite"] == "color"}
    assert color_after == color_before
    assert len(after["fixtures"]) == len(doc["fixtures"])

    # 只有 color 套件的产物被（重）写出。
    for rel in recorder.written:
        if rel == gen_fixtures.MANIFEST_PATH:
            continue
        assert rel.startswith("fixtures/color-"), rel


def test_full_run_writes_only_suite_products(recorder):
    """全集运行：每件 fixture 恰好写一次，且都落在 `fixtures/` 下。"""
    written, kept, failures = gen_fixtures.generate(None, keep_existing=False)
    assert failures == []
    assert kept == 0
    products = [rel for rel in recorder.written if rel != gen_fixtures.MANIFEST_PATH]
    assert len(products) == written == len(gen_fixtures.FIXTURES)
    assert len(set(products)) == len(products)
    for rel in products:
        assert rel.startswith("fixtures/") and rel.endswith(".json"), rel


def test_empty_selection_fails():
    """`--suite` 选不到任何 fixture 时必须失败，不是"0 件也算通过"。"""
    written, kept, failures = gen_fixtures.generate(["no-such-suite"], keep_existing=False)
    assert written == 0
    assert failures


def test_partial_run_without_a_committed_manifest_still_works(recorder, monkeypatch):
    """首次部分运行（还没有清单）不该崩，也不该假装保留了什么。"""
    monkeypatch.setattr(gen_fixtures, "_load_manifest", lambda: None)
    written, kept, failures = gen_fixtures.generate(["color"], keep_existing=True)
    assert failures == []
    assert kept == 0
    assert written == len([f for f in gen_fixtures.FIXTURES if f[0] == "color"])


def test_unknown_suite_is_rejected_by_the_cli():
    proc = subprocess.run(
        [sys.executable, "-X", "utf8",
         os.path.join(REPO_ROOT, "tools", "gen_fixtures.py"), "--suite", "nope"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.returncode != 0
    assert "nope" in proc.stdout.decode("utf-8", "replace")
