"""命令行入口。

**参数面一次定死**（`plan/03` §二）：M1–M5 只接实现，不改旗标——否则文档写好的用法
会在下一棒被 parser 拒掉（`references/release.md` 的"文档化的多值参数被 parser 拒绝"）。

退出码只在 `exitcodes.py` 定义；本模块只做映射，不复述规则。

**输出落点合同（决策 D20）**：落点**不是参数**。`--json` / `--md` 是开关，写到固定的
`out/report.json` 与 `out/report.md`；`oracle` 写到固定的 `out/oracle-report.{json,md}`。
路径由模块级常量拼出，`argv` 只决定"写不写"，不决定"写到哪"。理由：① 报告按设计不含
用户主目录绝对路径（`data/README.md` §8.7），输出面同样固定；② 本工具的用法是"在项目
目录里跑、把报告放进项目的 `out/`"；③ 落点不来自外部输入，就没有"参数拼路径"这一类面。
默认仍只打 stdout——`out/` 必须已存在（不静默建目录），否则 exit 3 且零副作用。
"""

import argparse
import io
import os
import sys

from bpreflight import __version__
from bpreflight import exitcodes
from bpreflight import input as input_mod
from bpreflight import pipeline
from bpreflight import thresholds
from bpreflight.gs1 import dictionary as dictionary_mod
from bpreflight.gs1 import vectors as vectors_mod
from bpreflight.report import render_json, render_md

PROG = "bpreflight"

REPORT_FORMATS = ("json", "md")

#: 内嵌数据装载失败一律走 exit 3（"字典缺失"是 §8.5 里明列的第三类 3）。
DATA_ERRORS = (
    input_mod.InputError,
    thresholds.ThresholdError,
    dictionary_mod.DictionaryError,
    vectors_mod.VectorError,
)

#: 固定落点。**不含任何来自 argv 的成分** —— 这是 D20 的结构性要求。
OUT_DIR = "out"
JSON_REPORT = os.path.join(OUT_DIR, "report.json")
MD_REPORT = os.path.join(OUT_DIR, "report.md")
ORACLE_JSON = os.path.join(OUT_DIR, "oracle-report.json")
ORACLE_MD = os.path.join(OUT_DIR, "oracle-report.md")


def build_parser():
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Barcode pre-press scanability auditor. Judges whether a barcode can be "
            "scanned from generation parameters alone (no image capture)."
        ),
        epilog=(
            "Reports go to stdout by default; --json/--md additionally write fixed "
            "paths under out/. Exit codes: 0 not crossed / 1 warn crossed / "
            "2 error crossed / 3 usage or unreadable input. See data/README.md 8.5."
        ),
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )

    sub = parser.add_subparsers(dest="command", metavar="{check,report,oracle}")
    sub.required = True

    def add_common(target):
        target.add_argument(
            "--input",
            metavar="SPEC.json",
            required=True,
            help="path to a JSON spec file (only .json; no content sniffing)",
        )
        target.add_argument(
            "--fail-on",
            choices=exitcodes.FAIL_ON_CHOICES,
            default="none",
            help="exit non-zero only when the worst severity crosses this gate (default: none)",
        )
        target.add_argument(
            "--strict-thresholds",
            action="store_true",
            help="treat unverified thresholds as errors instead of downgrading them to warn",
        )
        target.add_argument(
            "--with-timestamp",
            action="store_true",
            help="add a timestamp and mark the report deterministic=false (default: no clock)",
        )

    check = sub.add_parser(
        "check",
        help="run M1+M2+M3 together and print/write the report",
        description="Run the full audit. Default output is the Markdown human report.",
    )
    add_common(check)
    check.add_argument(
        "--json",
        action="store_true",
        help="also write {} (fixed path; requires the directory to exist)".format(JSON_REPORT),
    )
    check.add_argument(
        "--md",
        action="store_true",
        help="also write {} (fixed path; requires the directory to exist)".format(MD_REPORT),
    )

    report = sub.add_parser(
        "report",
        help="render one report format to stdout",
        description="Render a single format to stdout. Unknown --format is rejected (exit 3).",
    )
    add_common(report)
    report.add_argument(
        "--format",
        choices=REPORT_FORMATS,
        default="md",
        help="stdout format (default: md)",
    )

    oracle = sub.add_parser(
        "oracle",
        help="[M5, optional] rasterize and decode with an external engine",
        description=(
            "Optional M5 consistency check. Writes fixed artifacts under out/. "
            "When no decoder is available this reports skipped=oracle_absent "
            "instead of inventing a result."
        ),
    )
    add_common(oracle)

    return parser


def _write_fixed(relative_path, text):
    """写固定落点。

    `relative_path` 是**模块级常量**（`JSON_REPORT` / `MD_REPORT` / `ORACLE_*`），
    不来自命令行。目录必须已存在 —— 失败路径零副作用，不静默建目录。
    """
    parent = os.path.dirname(relative_path)
    if not os.path.isdir(parent):
        raise input_mod.InputError(
            "output directory {!r} does not exist (create it first); reports are "
            "written to fixed paths, not to a path given on the command line".format(
                parent
            )
        )
    with io.open(relative_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _emit(argv, parser):
    """返回 (exit_code)。所有失败都收敛到这里，保证失败面不长得像成功。"""
    args = parser.parse_args(argv)

    try:
        payload, input_info = input_mod.load_spec(args.input)
        rep = pipeline.run(
            payload,
            input_info,
            strict_thresholds=args.strict_thresholds,
            with_timestamp=args.with_timestamp,
        )
    except DATA_ERRORS as exc:
        sys.stderr.write("{}: error: {}\n".format(PROG, exc))
        return exitcodes.EXIT_USAGE

    json_text, _ = render_json.render_json(rep)
    md_text, _ = render_md.render_md(rep)

    try:
        if args.command == "check":
            wrote = False
            if args.json:
                _write_fixed(JSON_REPORT, json_text)
                wrote = True
            if args.md:
                _write_fixed(MD_REPORT, md_text)
                wrote = True
            if not wrote:
                sys.stdout.write(md_text)
        elif args.command == "report":
            sys.stdout.write(json_text if args.format == "json" else md_text)
        elif args.command == "oracle":
            # M5 未实现：不伪造 oracle 结论，只如实标注缺席。
            skip_text = (
                "schema: bpreflight/oracle-report/1\n"
                "skipped: oracle_absent\n"
                "reason: M5 not implemented in this milestone\n"
            )
            _write_fixed(ORACLE_JSON, json_text)
            _write_fixed(ORACLE_MD, skip_text)
            sys.stdout.write(md_text)
    except DATA_ERRORS as exc:
        sys.stderr.write("{}: error: {}\n".format(PROG, exc))
        return exitcodes.EXIT_USAGE

    return exitcodes.exit_code(args.fail_on, rep.worst_severity)


def main(argv=None):
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    return _emit(argv, parser)
