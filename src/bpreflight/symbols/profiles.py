"""Loader for `data/vectors/symbol_profiles.json` — the single reading point for M2.

为什么要有这一层（与 `gs1/vectors.py`、`thresholds.py` 同一性质）：判定模块不许自己
`open()` 数据文件，否则"阈值/规则零硬编码"只是口头约定。`pipeline` 在这里装载一次，
把 `ProfileBook` 传给 `symbols/feasibility.py`。

三态纪律（与 `data/README.md` §8.2 对齐）：每条规则必须带 `source` / `status` /
`verified_at`；`verified` 必须有日期，`unverified` 必须为 `null`。本轮没有取到任何
符号规范原文，因此数据文件里全部是 `unverified`（`plan/HANDOFF-M2` §三.1）。

`tie_break` 只实现了 `longest-first`；数据文件写成别的值会在装载期直接报错
（fail-closed：不支持的口径不允许静默降级成"随便切"）。
"""

import hashlib
import io
import json

from bpreflight import paths

PROFILE_FILE = "symbol_profiles.json"

STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "unverified"
STATUSES = (STATUS_VERIFIED, STATUS_UNVERIFIED)

TIE_BREAK_LONGEST_FIRST = "longest-first"
SUPPORTED_TIE_BREAKS = (TIE_BREAK_LONGEST_FIRST,)

MODULE_KINDS = ("fixed", "code128", "code39", "matrix")
DATA_SHAPES = ("raw", "gs1", "retail-gtin")
GS1_MODES = ("native", "requires-fnc1-flag", "unsupported", "not-modelled", "retail-gtin")

_REQUIRED_DOC_KEYS = ("schema", "version", "tie_break", "sources", "symbols")
_REQUIRED_RULE_FIELDS = ("source", "status", "verified_at")


class ProfileError(Exception):
    """The bundled profile table is missing or malformed (install problem, exit 3)."""


class SymbolProfile(object):
    """One symbol's rule set. Read-only view over the validated JSON object."""

    __slots__ = ("name", "raw")

    def __init__(self, name, raw):
        self.name = name
        self.raw = raw

    @property
    def family(self):
        return self.raw["family"]

    @property
    def data_shape(self):
        return self.raw["data_shape"]

    @property
    def identifier_ai(self):
        return self.raw.get("identifier_ai")

    @property
    def gtin_map(self):
        return self.raw.get("gtin_map")

    @property
    def gs1(self):
        return self.raw["gs1"]

    @property
    def charsets(self):
        return self.raw["charsets"]

    @property
    def length(self):
        return self.raw["length"]

    @property
    def modes(self):
        return self.raw["modes"]

    @property
    def modules(self):
        return self.raw["modules"]

    @property
    def checksum(self):
        return self.raw["checksum"]


class ProfileBook(object):
    """Loaded + validated profile table (immutable snapshot)."""

    def __init__(self, doc, sha256):
        self.doc = doc
        self.sha256 = sha256
        self.version = doc["version"]
        self.tie_break = doc["tie_break"]
        self.sources = dict(doc["sources"])
        self._symbols = {}
        for name in sorted(doc["symbols"]):
            self._symbols[name] = SymbolProfile(name, doc["symbols"][name])

    def names(self):
        return tuple(sorted(self._symbols))

    def require(self, name):
        try:
            return self._symbols[name]
        except KeyError:
            raise ProfileError(
                "symbol {!r} is not in {} (known: {})".format(
                    name, PROFILE_FILE, ", ".join(self.names())
                )
            )

    def source_text(self, key):
        try:
            return self.sources[key]
        except KeyError:
            raise ProfileError(
                "{} references undeclared source {!r}".format(PROFILE_FILE, key)
            )


_CACHE = {}


def load():
    """Read, digest and validate the bundled profile table."""
    if PROFILE_FILE in _CACHE:
        return _CACHE[PROFILE_FILE]
    path = paths.vector_path(PROFILE_FILE)
    try:
        with io.open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise ProfileError(
            "cannot read bundled vector {!r}: {} (incomplete install?)".format(
                PROFILE_FILE, exc.strerror or exc
            )
        )
    try:
        doc = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise ProfileError("bundled vector {!r} is not valid JSON: {}".format(PROFILE_FILE, exc))
    _validate(doc)
    book = ProfileBook(doc, hashlib.sha256(raw).hexdigest())
    _CACHE[PROFILE_FILE] = book
    return book


# --------------------------------------------------------------------------- #
# validation: 一条规则都不能"没有来源地"存在
# --------------------------------------------------------------------------- #


def _validate_rule(where, entry, sources):
    if not isinstance(entry, dict):
        raise ProfileError("{} must be an object".format(where))
    for field in _REQUIRED_RULE_FIELDS:
        if field not in entry:
            raise ProfileError(
                "{} misses {!r} (see data/README.md §8.10)".format(where, field)
            )
    if entry["status"] not in STATUSES:
        raise ProfileError("{} has unknown status {!r}".format(where, entry["status"]))
    if entry["status"] == STATUS_VERIFIED and not entry["verified_at"]:
        raise ProfileError("{} is status=verified but verified_at is empty".format(where))
    if entry["status"] != STATUS_VERIFIED and entry["verified_at"] is not None:
        raise ProfileError(
            "{} is status={} but verified_at is not null".format(where, entry["status"])
        )
    if entry["source"] not in sources:
        raise ProfileError(
            "{} references undeclared source {!r}".format(where, entry["source"])
        )


def _validate_charset(where, entry, sources):
    _validate_rule(where, entry, sources)
    if "characters" not in entry and "ranges" not in entry:
        raise ProfileError("{} needs 'characters' or 'ranges'".format(where))
    ranges = entry.get("ranges")
    if ranges is not None:
        for pair in ranges:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ProfileError("{} ranges must be [low, high] pairs".format(where))
            if pair[0] > pair[1]:
                raise ProfileError("{} has a reversed range {!r}".format(where, pair))


def _validate_length(where, entry, sources):
    _validate_rule(where, entry, sources)
    kind = entry.get("kind")
    if kind == "exact":
        if not isinstance(entry.get("exact"), int):
            raise ProfileError("{} exact length must be an int".format(where))
    elif kind == "range":
        for field in ("min", "max"):
            if not isinstance(entry.get(field), int):
                raise ProfileError("{} range needs int {!r}".format(where, field))
        if entry["min"] > entry["max"]:
            raise ProfileError("{} has min > max".format(where))
    else:
        raise ProfileError("{} has unknown length kind {!r}".format(where, kind))


def _validate_modes(where, raw, sources):
    modes = raw.get("modes")
    if not isinstance(modes, list) or not modes:
        raise ProfileError("{} needs a non-empty modes list".format(where))
    names = set()
    for index, mode in enumerate(modes):
        mode_where = "{}.modes[{}]".format(where, index)
        _validate_rule(mode_where, mode, sources)
        name = mode.get("name")
        if not name or name in names:
            raise ProfileError("{} has a missing/duplicate mode name {!r}".format(mode_where, name))
        names.add(name)
        if mode.get("charset") not in raw["charsets"]:
            raise ProfileError(
                "{} references unknown charset {!r}".format(mode_where, mode.get("charset"))
            )
        for field in ("group_size", "min_run", "priority"):
            if not isinstance(mode.get(field), int) or mode[field] < 1:
                raise ProfileError("{} needs a positive int {!r}".format(mode_where, field))
    if raw["modules"]["kind"] == "matrix":
        for index, mode in enumerate(modes):
            for field in ("group_bits", "header_bits", "count_bits"):
                if not isinstance(mode.get(field), int):
                    raise ProfileError(
                        "{}.modes[{}] needs int {!r} for a matrix symbol".format(
                            where, index, field
                        )
                    )


def _validate_modules(where, entry, sources):
    _validate_rule(where, entry, sources)
    kind = entry.get("kind")
    if kind not in MODULE_KINDS:
        raise ProfileError("{} has unknown modules kind {!r}".format(where, kind))
    if kind == "fixed":
        if not isinstance(entry.get("total"), int) or entry["total"] < 1:
            raise ProfileError("{} needs a positive int 'total'".format(where))
    elif kind == "code128":
        for field in (
            "start_modules",
            "modules_per_codeword",
            "check_modules",
            "stop_modules",
            "switch_codewords",
        ):
            if not isinstance(entry.get(field), int):
                raise ProfileError("{} needs int {!r}".format(where, field))
    elif kind == "code39":
        for field in ("modules_per_character", "inter_character_gap", "start_stop_characters"):
            if not isinstance(entry.get(field), int):
                raise ProfileError("{} needs int {!r}".format(where, field))
    else:  # matrix
        table = entry.get("table")
        if not isinstance(table, list) or not table:
            raise ProfileError("{} needs a non-empty size table".format(where))
        if not isinstance(entry.get("bits_per_codeword"), int):
            raise ProfileError("{} needs int 'bits_per_codeword'".format(where))
        for index, row in enumerate(table):
            for field in ("side", "data_codewords"):
                if not isinstance(row.get(field), int) or row[field] < 1:
                    raise ProfileError(
                        "{}.table[{}] needs a positive int {!r}".format(where, index, field)
                    )


def _validate_symbol(where, raw, sources):
    if not isinstance(raw, dict):
        raise ProfileError("{} must be an object".format(where))
    for key in (
        "family",
        "data_shape",
        "gs1",
        "charsets",
        "length",
        "modes",
        "modules",
        "checksum",
    ):
        if key not in raw:
            raise ProfileError("{} misses {!r}".format(where, key))
    if raw["data_shape"] not in DATA_SHAPES:
        raise ProfileError("{} has unknown data_shape {!r}".format(where, raw["data_shape"]))
    if raw["gs1"].get("mode") not in GS1_MODES:
        raise ProfileError("{} has unknown gs1.mode {!r}".format(where, raw["gs1"].get("mode")))
    _validate_rule(where + ".gs1", raw["gs1"], sources)

    if not isinstance(raw["charsets"], dict) or not raw["charsets"]:
        raise ProfileError("{} needs a non-empty charsets object".format(where))
    for name in sorted(raw["charsets"]):
        _validate_charset("{}.charsets.{}".format(where, name), raw["charsets"][name], sources)

    _validate_length(where + ".length", raw["length"], sources)
    _validate_modules(where + ".modules", raw["modules"], sources)
    _validate_rule(where + ".checksum", raw["checksum"], sources)
    if not raw["checksum"].get("kind"):
        raise ProfileError("{} checksum needs 'kind'".format(where))

    if raw["data_shape"] == "retail-gtin":
        mapping = raw.get("gtin_map")
        if not isinstance(mapping, dict):
            raise ProfileError("{} retail-gtin needs a gtin_map".format(where))
        _validate_rule(where + ".gtin_map", mapping, sources)
        for field in ("from_length", "target_length", "zero_padding_width"):
            if not isinstance(mapping.get(field), int) or mapping[field] < 1:
                raise ProfileError("{} gtin_map needs a positive int {!r}".format(where, field))

    _validate_modes(where, raw, sources)


def _validate(doc):
    if not isinstance(doc, dict):
        raise ProfileError("{} root must be an object".format(PROFILE_FILE))
    for key in _REQUIRED_DOC_KEYS:
        if key not in doc:
            raise ProfileError("{} misses top-level {!r}".format(PROFILE_FILE, key))
    if not isinstance(doc["sources"], dict) or not doc["sources"]:
        raise ProfileError("{} sources must be a non-empty object".format(PROFILE_FILE))
    if doc["tie_break"] not in SUPPORTED_TIE_BREAKS:
        raise ProfileError(
            "{} declares tie_break {!r}; only {} is implemented (refusing to guess)".format(
                PROFILE_FILE, doc["tie_break"], ", ".join(SUPPORTED_TIE_BREAKS)
            )
        )
    symbols = doc["symbols"]
    if not isinstance(symbols, dict) or not symbols:
        raise ProfileError("{} symbols must be a non-empty object".format(PROFILE_FILE))
    for name in sorted(symbols):
        _validate_symbol("symbols." + name, symbols[name], doc["sources"])
