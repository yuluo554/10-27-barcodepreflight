"""阈值装载器——**全仓唯一**读取 `data/vectors/*.json` 的地方。

判定模块接收这里装载好的对象，不自己读文件。这样"阈值零硬编码"才是结构性质，
而不是靠自觉（`tools/check_thresholds.py` 常驻守门）。

三态纪律（`data/README.md` §8.2、`plan/04` §三）：

- `gen-spec` 项必须有 `source` / `status` / `verified_at` / `basis`；
- `engineering-heuristic` 项**没有** `status`，不参与未核降级；
- 缺字段即 `ThresholdError`（调用方映射为 exit 3）——不留无主阈值。
"""

import hashlib
import io
import json
import os

from bpreflight import paths

#: 参与装载的向量文件（固定序，输出可复现）。
#: `color_cases.json`（M3）与两个阈值文件同一装载点：照明建模表既驱动判定
#: （哪些照明可判），又必须与阈值册同一份快照身份，否则报告里的 `vectors_sha256`
#: 说不清"哪份照明表判的"。
THRESHOLD_FILES = ("quiet_zone.json", "gen_spec.json", "color_cases.json")

STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "unverified"

BASIS_GEN_SPEC = "gen-spec"
BASIS_ENGINEERING = "engineering-heuristic"

_REQUIRED_GEN_SPEC_FIELDS = ("source", "status", "verified_at", "basis")


class ThresholdError(Exception):
    """阈值文件缺失或形状不合契约。调用方映射为 exit 3。"""


class ThresholdBook(object):
    """装载好的阈值册：只读快照 + 未核项清单。"""

    def __init__(self, quiet_zone, gen_spec, sha256, color_cases=None):
        self.quiet_zone = quiet_zone
        self.gen_spec = gen_spec
        self.color_cases = color_cases or {}
        self.sha256 = sha256

    # ---- 查值 ----

    def gen_spec_entry(self, key):
        try:
            return self.gen_spec["values"][key]
        except KeyError:
            raise ThresholdError(
                "gen_spec.json misses values.{} (known: {})".format(
                    key, ", ".join(sorted(self.gen_spec.get("values", {})))
                )
            )

    def quiet_zone_entry(self, symbol, side):
        symbols = self.quiet_zone.get("symbols", {})
        if symbol not in symbols:
            raise ThresholdError(
                "quiet_zone.json misses symbol {!r} (known: {})".format(
                    symbol, ", ".join(sorted(symbols))
                )
            )
        sides = symbols[symbol]
        if side not in sides:
            raise ThresholdError(
                "quiet_zone.json misses side {!r} for {!r}".format(side, symbol)
            )
        return sides[side]

    def engineering(self, key):
        try:
            return self.gen_spec["engineering_heuristics"][key]
        except KeyError:
            raise ThresholdError(
                "gen_spec.json misses engineering_heuristics.{} (known: {})".format(
                    key, ", ".join(sorted(self.gen_spec.get("engineering_heuristics", {})))
                )
            )

    def illumination(self, name):
        """One illumination model; unknown names are *unmodelled*, not an error.

        Returning an unmodelled entry (rather than raising) is deliberate: an odd
        illumination is a property of the user's spec, so it must become
        `info: surface_effect_unmodeled` (§8.9 G5), not an install-time exit 3.
        """
        models = self.color_cases.get("illuminations", {})
        return models.get(name, {"modelled": False, "note": "illumination not in the table"})

    @property
    def mm_per_inch(self):
        """Unit conversion, taken from the data file like any other constant."""
        try:
            return self.gen_spec["constants"]["mm_per_inch"]
        except KeyError:
            raise ThresholdError("gen_spec.json misses constants.mm_per_inch")

    # ---- 三态 ----

    def unverified_keys(self):
        """所有 `status == unverified` 的 gen-spec 项，按点路径排序。"""
        found = []
        for symbol in sorted(self.quiet_zone.get("symbols", {})):
            for side in sorted(self.quiet_zone["symbols"][symbol]):
                entry = self.quiet_zone["symbols"][symbol][side]
                if entry.get("status") == STATUS_UNVERIFIED:
                    found.append("quiet_zone.{}.{}".format(symbol, side))
        for key in sorted(self.gen_spec.get("values", {})):
            entry = self.gen_spec["values"][key]
            if entry.get("status") == STATUS_UNVERIFIED:
                found.append("gen_spec.{}".format(key))
        return sorted(found)

    def status_of(self, entry):
        """gen-spec 项的 status；engineering-heuristic 项恒 `not-applicable`。"""
        if entry.get("basis") == BASIS_ENGINEERING:
            return "not-applicable"
        return entry.get("status")


def _validate_gen_spec_item(where, entry):
    for field in _REQUIRED_GEN_SPEC_FIELDS:
        if field not in entry:
            raise ThresholdError(
                "{} misses required field {!r} (see data/README.md §8.2)".format(
                    where, field
                )
            )
    if entry["status"] == STATUS_VERIFIED and not entry["verified_at"]:
        raise ThresholdError(
            "{} is status=verified but verified_at is empty".format(where)
        )
    if entry["status"] != STATUS_VERIFIED and entry["verified_at"] is not None:
        raise ThresholdError(
            "{} is status={} but verified_at is not null".format(where, entry["status"])
        )
    if entry["basis"] == BASIS_ENGINEERING:
        raise ThresholdError(
            "{} is under gen-spec values but declares basis=engineering-heuristic".format(
                where
            )
        )


def _validate_quiet_zone(doc):
    if "symbols" not in doc:
        raise ThresholdError("quiet_zone.json misses top-level 'symbols'")
    if not doc["symbols"]:
        raise ThresholdError("quiet_zone.json has zero symbols (empty data is not a pass)")
    for symbol in sorted(doc["symbols"]):
        sides = doc["symbols"][symbol]
        for side in sorted(sides):
            where = "quiet_zone.symbols.{}.{}".format(symbol, side)
            _validate_gen_spec_item(where, sides[side])
            # `required` 是结构事实（该侧是否要求静区），不是标准数值：
            # `quiet_zone_absent` 只读它，因此必须在数据里显式声明，
            # 不能由 `modules_min > 0` 推断（那会把"未核阈值"变成结构事实）。
            if not isinstance(sides[side].get("required"), bool):
                raise ThresholdError(
                    "{} misses boolean 'required' (see data/README.md §8.2)".format(where)
                )
            if not isinstance(sides[side].get("modules_min"), int):
                raise ThresholdError("{} modules_min must be an int".format(where))


def _validate_gen_spec(doc):
    if "values" not in doc:
        raise ThresholdError("gen_spec.json misses top-level 'values'")
    if not doc["values"]:
        raise ThresholdError("gen_spec.json has zero values (empty data is not a pass)")
    for key in sorted(doc["values"]):
        _validate_gen_spec_item("gen_spec.values.{}".format(key), doc["values"][key])
    if "engineering_heuristics" not in doc:
        raise ThresholdError("gen_spec.json misses 'engineering_heuristics'")
    for key in sorted(doc["engineering_heuristics"]):
        entry = doc["engineering_heuristics"][key]
        # K8：工程判据**不得**带 status，否则"未核降级"会漏进来。
        if key == "note":
            continue
        if not isinstance(entry, dict):
            raise ThresholdError("gen_spec.engineering_heuristics.{} must be an object".format(key))
        if "status" in entry or "verified_at" in entry:
            raise ThresholdError(
                "gen_spec.engineering_heuristics.{} must not carry status/verified_at "
                "(engineering heuristics never downgrade; see data/README.md §8.2)".format(key)
            )
        if entry.get("basis") != "engineering-heuristic":
            raise ThresholdError(
                "gen_spec.engineering_heuristics.{} must declare basis=engineering-heuristic".format(
                    key
                )
            )
    if "constants" not in doc or "mm_per_inch" not in doc["constants"]:
        raise ThresholdError("gen_spec.json misses constants.mm_per_inch")


def _validate_color_cases(doc):
    """照明建模表 + 用例。工程判据 ⇒ 这里**不许**出现 status（K8）。"""
    if "illuminations" not in doc or not doc["illuminations"]:
        raise ThresholdError("color_cases.json misses a non-empty 'illuminations'")
    for name in sorted(doc["illuminations"]):
        entry = doc["illuminations"][name]
        if not isinstance(entry, dict) or "modelled" not in entry:
            raise ThresholdError(
                "color_cases.illuminations.{} needs a 'modelled' flag".format(name)
            )
        if not isinstance(entry["modelled"], bool):
            raise ThresholdError(
                "color_cases.illuminations.{}.modelled must be a bool".format(name)
            )
        if "status" in entry or "verified_at" in entry:
            raise ThresholdError(
                "color_cases.illuminations.{} must not carry status/verified_at "
                "(engineering heuristics never downgrade)".format(name)
            )
    if not doc.get("cases"):
        raise ThresholdError("color_cases.json has zero cases (empty data is not a pass)")
    for index, case in enumerate(doc["cases"]):
        where = "color_cases.cases[{}]".format(index)
        for field in ("name", "bar_color", "space_color", "illumination", "expected"):
            if field not in case:
                raise ThresholdError("{} misses {!r}".format(where, field))
        if not isinstance(case["expected"], list):
            raise ThresholdError("{} expected must be a list of finding ids".format(where))


def load_book():
    """装载 + 校验三个阈值/模型文件。缺文件/形状不对一律 `ThresholdError`。"""
    docs = {}
    digest = hashlib.sha256()
    for name in THRESHOLD_FILES:
        path = paths.vector_path(name)
        try:
            with io.open(path, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            raise ThresholdError(
                "cannot read bundled vector {!r}: {} (incomplete install?)".format(
                    name, exc.strerror or exc
                )
            )
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(raw)
        try:
            docs[name] = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise ThresholdError("bundled vector {!r} is not valid JSON: {}".format(name, exc))

    _validate_quiet_zone(docs["quiet_zone.json"])
    _validate_gen_spec(docs["gen_spec.json"])
    _validate_color_cases(docs["color_cases.json"])
    return ThresholdBook(
        docs["quiet_zone.json"],
        docs["gen_spec.json"],
        digest.hexdigest(),
        docs["color_cases.json"],
    )


def find_book(explicit_dir=None):
    """装载阈值册；`explicit_dir` 给了就只认它（无效即报错，不回退）。"""
    if explicit_dir is None:
        return load_book()
    for name in THRESHOLD_FILES:
        if not os.path.isfile(os.path.join(explicit_dir, name)):
            raise ThresholdError(
                "explicit threshold dir {!r} misses {!r}; refusing to fall back to the "
                "bundled copy".format(explicit_dir, name)
            )
    raise ThresholdError(
        "explicit threshold dirs are not supported yet; omit --thresholds-dir "
        "(bundled vectors at {} are the only source)".format(paths.VECTORS_DIR)
    )
