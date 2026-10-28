"""M5 · 模块图案表：装载点 + 「字符流 → 模块行」的唯一构造。

为什么图案也要放数据里：采样器必须是**纯函数**（`plan/HANDOFF-M5` §二.8），不读文件；
因此图案表由本模块装载成 `LayoutBook`，与 `ThresholdBook` / `ProfileBook` 同一性质。
本轮没有取到任何符号规范原文（`iso.org` / `gs1.org` 403），所以每条恒为 `unverified`，
文档不得把这些图案写成规范要求（`data/README.md` §9）。

只实现数据里**声明过**的派生规则（`R = complement(L)`、`G = reverse(complement(L))`）：
认不出的规则名一律报错（fail-closed）——"看不懂就跳过"会让图案悄悄漂移。
按表建模之外的符号（`ean8` / `upca` / 2D 等）不采样，由编排层落
`skipped: sampler_unsupported:<symbol>`。
"""

import hashlib
import io
import json

from bpreflight import paths

PATTERN_FILE = "sampler_patterns.json"

STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "unverified"
STATUSES = (STATUS_VERIFIED, STATUS_UNVERIFIED)

#: 派生规则名（数据里 `derivations` 的值）。只有这两条被实现。
DERIVATION_COMPLEMENT = "complement(L)"
DERIVATION_REVERSE_COMPLEMENT = "reverse(complement(L))"
DERIVATIONS = (DERIVATION_COMPLEMENT, DERIVATION_REVERSE_COMPLEMENT)

BASE_SET = "L"
DERIVED_SETS = ("G", "R")

DIGITS = "0123456789"

#: 模块行里的两种状态（1 = 条，0 = 空）。
BAR = 1
SPACE = 0


class LayoutError(Exception):
    """图案表缺失或形状不合契约。调用方映射为 exit 3（安装问题，不是关于条码的结论）。"""


class Layout(object):
    """一个符号的模块图案表（只读视图）。"""

    __slots__ = ("symbol", "raw", "codes", "parity")

    def __init__(self, symbol, raw, codes, parity):
        self.symbol = symbol
        self.raw = raw
        self.codes = codes
        self.parity = parity

    # ---- 形状 ----

    @property
    def modules_total(self):
        return self.raw["modules_total"]

    @property
    def digits_required(self):
        return self.raw["digits_required"]

    @property
    def left_digits(self):
        return self.raw["left_digits"]

    @property
    def right_digits(self):
        return self.raw["right_digits"]

    @property
    def status(self):
        return self.raw["status"]

    @property
    def source(self):
        return self.raw["source"]

    def code_length(self):
        return len(self.codes[BASE_SET][0])

    # ---- 构造 ----

    def row_for(self, text):
        """`text`（该符号的字符流）→ 模块行（`0`/`1` 的 list，长度 = `modules_total`）。

        结构：`start` 守卫 + 前 `left_digits` 位（码集由首位选出的 parity 行决定）
        + `middle` 守卫 + 后 `right_digits` 位（一律 `R`）+ `end` 守卫。
        任何不符合该结构的输入都报 `LayoutError`，**不产出**半条模块行。
        """
        if not isinstance(text, str):
            raise LayoutError("sampler text must be a string, got {!r}".format(type(text).__name__))
        if len(text) != self.digits_required:
            raise LayoutError(
                "{} needs {} characters, got {} ({!r})".format(
                    self.symbol, self.digits_required, len(text), text
                )
            )
        for character in text:
            if character not in DIGITS:
                raise LayoutError(
                    "{} sampler table only covers digits, got {!r}".format(
                        self.symbol, character
                    )
                )
        parity_row = self.parity.get(text[0])
        if parity_row is None:
            raise LayoutError(
                "{} has no parity row for leading digit {!r}".format(self.symbol, text[0])
            )

        guards = self.raw["guards"]
        left = text[1 : 1 + self.left_digits]
        right = text[1 + self.left_digits :]

        parts = [guards["start"]]
        for index, character in enumerate(left):
            parts.append(self._code(parity_row[index], character))
        parts.append(guards["middle"])
        for character in right:
            parts.append(self._code("R", character))
        parts.append(guards["end"])

        row = "".join(parts)
        if len(row) != self.modules_total:
            raise LayoutError(
                "{}.modules_total is {} but the pattern builds {} modules".format(
                    self.symbol, self.modules_total, len(row)
                )
            )
        return [BAR if character == "1" else SPACE for character in row]

    def _code(self, set_name, character):
        try:
            table = self.codes[set_name]
        except KeyError:
            raise LayoutError(
                "{}.code_sets misses {} (known: {})".format(
                    self.symbol, set_name, ", ".join(sorted(self.codes))
                )
            )
        return table[DIGITS.index(character)]


class LayoutBook(object):
    """装载好的图案册（只读快照 + 身份摘要）。"""

    __slots__ = ("doc", "sha256", "version", "_symbols")

    def __init__(self, doc, sha256):
        self.doc = doc
        self.sha256 = sha256
        self.version = doc.get("version")
        self._symbols = {
            name: _build_layout(name, doc["symbols"][name], doc.get("sources", {}))
            for name in sorted(doc["symbols"])
        }

    def names(self):
        return sorted(self._symbols)

    def has(self, symbol):
        return symbol in self._symbols

    def layout(self, symbol):
        try:
            return self._symbols[symbol]
        except KeyError:
            raise LayoutError(
                "sampler_patterns.json has no layout for {!r} (known: {})".format(
                    symbol, ", ".join(self.names())
                )
            )


# --------------------------------------------------------------------------- #
# 装载与校验
# --------------------------------------------------------------------------- #


def _check_code(text, where, width):
    if not isinstance(text, str) or len(text) != width:
        raise LayoutError("{} must be a {}-module string".format(where, width))
    if set(text) - {"0", "1"}:
        raise LayoutError("{} must contain only '0'/'1', got {!r}".format(where, text))


def _check_guard(text, where):
    if not isinstance(text, str) or not text:
        raise LayoutError("{} must be a non-empty '0'/'1' string".format(where))
    if set(text) - {"0", "1"}:
        raise LayoutError("{} must contain only '0'/'1', got {!r}".format(where, text))


def _build_layout(name, raw, sources):
    """校验一条图案表并派生数据里声明过的码集。

    派生 `R` = `complement(L)`、`G` = `reverse(complement(L))`：**不**在数据里抄第二份，
    否则 L/G/R 三份表可以互相矛盾而没人发现（与"校验位不复制第二份"同一理由）。
    """
    where = "sampler_patterns.symbols.{}".format(name)
    for field in ("family", "parity_digits", "left_digits", "right_digits",
                  "digits_required", "modules_total", "guards", "code_sets",
                  "derivations", "source", "status", "verified_at"):
        if field not in raw:
            raise LayoutError("{} misses {!r}".format(where, field))
    if raw["status"] not in STATUSES:
        raise LayoutError("{}.status must be one of {}".format(where, "/".join(STATUSES)))
    if raw["status"] == STATUS_VERIFIED and not raw["verified_at"]:
        raise LayoutError("{} is status=verified but verified_at is empty".format(where))
    if raw["status"] != STATUS_VERIFIED and raw["verified_at"] is not None:
        raise LayoutError("{} is status={} but verified_at is not null".format(
            where, raw["status"]))
    if raw["source"] not in sources:
        raise LayoutError(
            "{}.source {!r} is not declared in sampler_patterns.json#sources".format(
                where, raw["source"]
            )
        )

    for field in ("parity_digits", "left_digits", "right_digits", "digits_required",
                  "modules_total"):
        value = raw[field]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise LayoutError("{}.{} must be a positive int".format(where, field))
    counted = raw["parity_digits"] + raw["left_digits"] + raw["right_digits"]
    if counted != raw["digits_required"]:
        raise LayoutError(
            "{}: parity+left+right = {} but digits_required = {}".format(
                where, counted, raw["digits_required"]
            )
        )

    guards = raw["guards"]
    if not isinstance(guards, dict):
        raise LayoutError("{}.guards must be an object".format(where))
    for side in ("start", "middle", "end"):
        if side not in guards:
            raise LayoutError("{}.guards misses {!r}".format(where, side))
        _check_guard(guards[side], "{}.guards.{}".format(where, side))

    code_sets = raw["code_sets"]
    if BASE_SET not in code_sets:
        raise LayoutError("{}.code_sets must declare the base set {!r}".format(where, BASE_SET))
    base = code_sets[BASE_SET]
    if not isinstance(base, list) or len(base) != len(DIGITS):
        raise LayoutError(
            "{}.code_sets.{} must be a list of {} entries".format(
                where, BASE_SET, len(DIGITS)
            )
        )
    width = len(base[0]) if base else 0
    if width == 0:
        raise LayoutError("{}.code_sets.{} is empty".format(where, BASE_SET))
    for index, code in enumerate(base):
        _check_code(code, "{}.code_sets.{}[{}]".format(where, BASE_SET, index), width)

    derivations = raw["derivations"]
    if not isinstance(derivations, dict):
        raise LayoutError("{}.derivations must be an object".format(where))
    codes = {BASE_SET: tuple(base)}
    derived = sorted(set(DERIVED_SETS) - set(derivations))
    if derived:
        raise LayoutError(
            "{} must declare derivations for {}".format(where, ", ".join(derived))
        )
    for set_name in DERIVED_SETS:
        rule = derivations[set_name]
        if rule not in DERIVATIONS:
            raise LayoutError(
                "{}.derivations.{} = {!r} is not implemented (known: {})".format(
                    where, set_name, rule, " | ".join(DERIVATIONS)
                )
            )
        codes[set_name] = tuple(_derive(rule, codes[BASE_SET]))

    parity = raw["parity_first_digit"]
    if not isinstance(parity, dict) or not parity:
        raise LayoutError("{}.parity_first_digit must be a non-empty object".format(where))
    # 1D 零售符号的 parity 表按首位索引：首位可能是 0..9 中任何一个，
    # 因此键集合必须覆盖 `DIGITS`（缺一个键 = 那个首位永远采不出模块行）。
    missing_keys = [digit for digit in DIGITS if digit not in parity]
    if missing_keys:
        raise LayoutError(
            "{}.parity_first_digit misses {} (the leading digit must always be covered)".format(
                where, ", ".join(missing_keys)
            )
        )
    for key in sorted(parity):
        row = parity[key]
        if key not in DIGITS:
            raise LayoutError("{}.parity_first_digit key {!r} is not a digit".format(where, key))
        if not isinstance(row, str) or len(row) != raw["left_digits"]:
            raise LayoutError(
                "{}.parity_first_digit.{} must be a {}-character string".format(
                    where, key, raw["left_digits"]
                )
            )
        if set(row) - {"L", "G"}:
            raise LayoutError(
                "{}.parity_first_digit.{} must use only L/G, got {!r}".format(where, key, row)
            )

    layout = Layout(name, raw, codes, parity)
    _check_total(layout, where)
    return layout


def _derive(rule, base):
    """实现数据里声明的两条派生规则（别的一律已在上游拒掉）。

    `complement(L)`：逐位取反；`reverse(complement(L))`：取反后**反转**。
    """
    complement = ["".join("1" if bit == "0" else "0" for bit in code) for code in base]
    if rule == DERIVATION_COMPLEMENT:
        return complement
    return [code[::-1] for code in complement]


def _check_total(layout, where):
    """图案长度必须与 `modules_total` 一致：用**结构**算，不靠人抄。"""
    guards = layout.raw["guards"]
    width = layout.code_length()
    total = (
        len(guards["start"])
        + layout.left_digits * width
        + len(guards["middle"])
        + layout.right_digits * width
        + len(guards["end"])
    )
    if total != layout.modules_total:
        raise LayoutError(
            "{}: guards + digits build {} modules but modules_total is {}".format(
                where, total, layout.modules_total
            )
        )


def load(doc=None):
    """装载图案册。缺文件 / 形状不对一律 `LayoutError`（调用方映射 exit 3）。"""
    if doc is None:
        path = paths.vector_path(PATTERN_FILE)
        try:
            with io.open(path, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            raise LayoutError(
                "cannot read bundled vector {!r}: {} (incomplete install?)".format(
                    PATTERN_FILE, exc.strerror or exc
                )
            )
        try:
            doc = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise LayoutError("bundled vector {!r} is not valid JSON: {}".format(
                PATTERN_FILE, exc))
        digest = hashlib.sha256(raw).hexdigest()
    else:
        digest = hashlib.sha256(
            json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    for key in ("schema", "symbols", "sources"):
        if key not in doc:
            raise LayoutError("{} misses top-level {!r}".format(PATTERN_FILE, key))
    if not doc["symbols"]:
        raise LayoutError("{} has zero symbols (empty data is not a pass)".format(PATTERN_FILE))
    if not doc["schema"].startswith("bpreflight/"):
        raise LayoutError("{} has an unexpected schema {!r}".format(PATTERN_FILE, doc["schema"]))
    return LayoutBook(doc, digest)