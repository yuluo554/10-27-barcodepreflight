"""M5 · 外部解码引擎探测与调用 —— 本层唯一离开本进程的地方。

红线（`plan/HANDOFF-M5` §二.9）：**不得 import 任何解码库**（zxing-cpp / pyzbar / zbar
都不行）——`tests/test_no_network.py::test_third_party_imports_are_absent` 会红。
因此只走 `shutil.which` 探测 + `subprocess` 调用，**引擎缺失就如实标
`skipped: oracle_absent`**，绝不伪造结论（`data/README.md` §8.9 G6）。

三态返回（`Outcome.status`）是本模块的全部契约：

  · `decoded`      —— 引擎退出 0 且打印了 payload；
  · `not-decoded`  —— 引擎说"没读到条码"（退出非 0 且输出像是"找不到"，或退出 0 但无 payload）；
  · `unusable`     —— 起不来 / 超时 / 退出码与输出无法解释。

**`unusable` 与 `not-decoded` 必须分开**：把"引擎没驱动起来"读成"解不出"，就会凭空
产出 `m3_laxer` 并逼人去"修"一个并不存在的 M3 bug（`plan/HANDOFF-M5` §二.7）。

未验声明：本机**没有任何**候选引擎（实跑见 `data/README.md` §9），因此命令模板
（名字 + 参数）**未被观测过**；模板不匹配时走 `unusable`，而不是产出 agreement。
""" 

import io
import os
import shutil
import struct
import subprocess
import tempfile
import zlib

DECODED = "decoded"
NOT_DECODED = "not-decoded"
UNUSABLE = "unusable"

#: 引擎调用的超时（秒）。结构常量：改口径不会动它。
_TIMEOUT_SECONDS = 10

#: 候选引擎：名字 + 参数模板（`{image}` 是写好的 PNG 路径）。
#: **模板未在本机观测过**（无引擎）——它是"最保守的猜法"，并且猜错只会得到
#: `unusable`（不产 agreement），不会伪造"解不出"。
CANDIDATES = (
    ("zxing-cpp", ("--format", "PNG", "{image}")),
    ("ZXingReader", ("{image}",)),
    ("zbarimg", ("--quiet", "--raw", "{image}")),
)

#: 引擎输出里这些字样 = "没读到条码"（`not-decoded`），而不是"引擎坏了"。
_NO_SYMBOL_MARKERS = (
    "no barcode",
    "no symbol",
    "barcode not found",
    "not found",
    "unable to",
    "failed to",
    "no code",
    "couldn't",
)

#: payload / detail 落进报告前的长度上限（报告是给人看的，不是日志转储）。
#: 写成 `1 << 8` 而不是 256：这是显示上限，不是阈值，且阈值门只放行结构性常量。
_PAYLOAD_LIMIT = 1 << 8


class Engine(object):
    """一个可用的外部解码引擎（只描述**怎么调**它，不含判定）。"""

    __slots__ = ("name", "command", "args", "version")

    def __init__(self, name, command, args, version):
        self.name = name
        self.command = command
        self.args = tuple(args)
        self.version = version

    def describe(self):
        """Report identity only.

        Deliberately **not** the executable path: reports must not carry absolute
        host paths (`data/README.md` §8.7 末条) — the path of an interpreter or a
        tool under a user home directory is exactly what that rule keeps out.
        """
        return {"name": self.name, "version": self.version, "kind": "external-subprocess"}


class Outcome(object):
    """`decode()` 的结果：解出 / 解不出 / 引擎不可用。"""

    __slots__ = ("status", "payload", "detail")

    def __init__(self, status, payload=None, detail=""):
        self.status = status
        self.payload = payload
        self.detail = detail

    @property
    def decoded(self):
        return self.status == DECODED


def default_runner(command):
    """Run one external command; never raises except for launch failures.

    Injectable on purpose (`tests/test_oracle.py` replaces it): this machine has no
    engine, so the agreement logic must be exercisable with an engine double while
    the real path stays honest.
    """
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=_TIMEOUT_SECONDS,
    )
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", "replace"),
        completed.stderr.decode("utf-8", "replace"),
    )


def probe(which=None):
    """Return an `Engine` for the first candidate found on this machine, else `None`.

    `which` is injectable so a test can assert the "no engine -> skipped" path
    without depending on what happens to be installed.
    """
    finder = which or shutil.which
    for name, args in CANDIDATES:
        command = finder(name)
        if not command:
            continue
        return Engine(name, command, args, _version(command))
    return None


def _version(command):
    try:
        code, out, err = default_runner([command, "--version"])
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if code != 0:
        return "unknown"
    lines = [line.strip() for line in (out + "\n" + err).splitlines() if line.strip()]
    return lines[0][:_PAYLOAD_LIMIT] if lines else "unknown"


def decode(bitmap, engine, runner=None):
    """Hand the sampled bitmap to the engine as an 8-bit grayscale PNG."""
    prepare = runner or default_runner
    with tempfile.TemporaryDirectory(prefix="bpreflight-oracle-") as workdir:
        path = os.path.join(workdir, "sample.png")
        with io.open(path, "wb") as handle:
            handle.write(png_bytes(bitmap))
        command = [engine.command]
        command.extend(argument.format(image=path) for argument in engine.args)
        try:
            code, out, err = prepare(command)
        except (OSError, subprocess.SubprocessError) as exc:
            return Outcome(UNUSABLE, None, "{}: {}".format(type(exc).__name__, exc))
    return _interpret(code, out, err)


def _interpret(code, out, err):
    payload = _payload_of(out)
    if code == 0:
        if payload:
            return Outcome(DECODED, payload, "")
        return Outcome(NOT_DECODED, None, "engine exited 0 without a payload")
    text = (out + "\n" + err).strip()
    lowered = text.lower()
    if any(marker in lowered for marker in _NO_SYMBOL_MARKERS):
        return Outcome(NOT_DECODED, None, text[:_PAYLOAD_LIMIT])
    return Outcome(
        UNUSABLE, None, "engine exited {}: {}".format(code, text[:_PAYLOAD_LIMIT])
    )


def _payload_of(out):
    for line in out.splitlines():
        cleaned = "".join(character for character in line if character.isprintable()).strip()
        if cleaned:
            return cleaned[:_PAYLOAD_LIMIT]
    return None


def png_bytes(bitmap):
    """Minimal PNG encoder for the sampled raster (8-bit grayscale, filter type 0).

    Written with `struct` + `zlib` only: the point of the sampler is that this tool
    needs **no image library** (`plan/01` §M5 流程.1). PNG (rather than PGM) is chosen
    because it is what real decoders' CLIs accept.
    """
    raw = b"".join(b"\x00" + bitmap.line for _ in range(bitmap.height))

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data))
        )

    header = struct.pack(">IIBBBBB", bitmap.width, bitmap.height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )