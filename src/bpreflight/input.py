"""输入装载：只收 JSON（决策 D14），按声明分派、未知即拒。

纪律（`references/delivery.md` CLI 参数语义四条）：

1. **不做内容嗅探**：扩展名不是 `.json` 直接拒（`pipeline` 会把它变成 exit 3）。
2. **显式给了路径就只认它**：读不到即报错，**不回退到任何内置样例**。
3. 未知 `schema` 值显式拒绝，并列出支持面。
4. 失败路径零副作用：本模块只读，不创建任何目录或文件。
"""

import hashlib
import json
import os

SPEC_SCHEMA = "bpreflight/spec/1"
SUPPORTED_SCHEMAS = (SPEC_SCHEMA,)

#: 首期符号集合（`plan/01` §7 范围限定）。其余符号 → `symbol_unsupported`。
SUPPORTED_SYMBOLS = (
    "code128",
    "gs1-128",
    "ean13",
    "ean8",
    "upca",
    "datamatrix",
    "qr",
    "code39",
)

ILLUMINATIONS = ("white", "red", "ir")

#: M1（数据层）判定所需的输入面：`gs1_element_string` 或裸 `identifier`，二选一。
DATA_FIELDS = ("gs1_element_string", "identifier")

#: M3（印刷层）判定所需的输入面。缺任一即 `input_incomplete`（§8.9 G3），
#: **不静默补默认值**。
PRINT_FIELDS = ("symbol", "x_dimension_mm", "target_dpi", "quiet_zone_mm")

_STRING_FIELDS = ("gs1_element_string", "identifier")


class InputError(Exception):
    """输入不可解析 / 不可接受。调用方一律映射为 exit 3。"""


def _read_bytes(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise InputError(
            "cannot read input {!r}: {} (no fallback to any bundled sample)".format(
                path, exc.strerror or exc
            )
        )


def load_spec(path):
    """读并校验 spec 文件，返回 `(spec_dict, input_info)`。

    `input_info` 只含**脱敏**信息：文件名（basename）+ sha256 + mode。
    **不写**绝对路径 / 主目录（`data/README.md` §8.7 末条）。
    """
    if not path:
        raise InputError("--input is required")
    if not path.lower().endswith(".json"):
        raise InputError(
            "unsupported input extension for {!r}: only .json is accepted "
            "(no content sniffing)".format(path)
        )

    raw = _read_bytes(path)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError("input {!r} is not valid UTF-8: {}".format(path, exc))

    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise InputError("input {!r} is not valid JSON: {}".format(path, exc))

    if not isinstance(payload, dict):
        raise InputError("input root must be a JSON object")

    schema = payload.get("schema")
    if schema not in SUPPORTED_SCHEMAS:
        raise InputError(
            "unsupported schema {!r}; supported: {}".format(
                schema, ", ".join(SUPPORTED_SCHEMAS)
            )
        )

    symbol = payload.get("symbol")
    if symbol is not None and symbol not in SUPPORTED_SYMBOLS:
        raise InputError(
            "unsupported symbol {!r}; supported: {}".format(
                symbol, ", ".join(SUPPORTED_SYMBOLS)
            )
        )

    illumination = payload.get("illumination")
    if illumination is not None and illumination not in ILLUMINATIONS:
        raise InputError(
            "unsupported illumination {!r}; supported: {}".format(
                illumination, ", ".join(ILLUMINATIONS)
            )
        )

    for field in _STRING_FIELDS:
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise InputError(
                "{!r} must be a string (got {})".format(field, type(value).__name__)
            )
        if value == "":
            raise InputError("{!r} is empty; omit the field or supply a value".format(field))

    input_info = {
        "file": os.path.basename(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "mode": payload.get("mode", "params"),
    }
    return payload, input_info


def missing_fields(payload):
    """M3 判定所需参数里缺了哪些（只报缺，不静默补默认值；§8.9 G3）。"""
    return [name for name in PRINT_FIELDS if payload.get(name) is None]
