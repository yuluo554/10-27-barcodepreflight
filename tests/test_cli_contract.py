"""CLI 契约：参数面反射对账 + 失败路径。

覆盖 `references/release.md`「README 指令面 → parser 的反射对账」：
README 里出现的每条命令都要能被真实 parser 解析（任一 exit 2 即红）。
"""

import pathlib
import re

import pytest

from bpreflight.cli import build_parser, main


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    assert "bpreflight" in capsys.readouterr().out


def test_version_flag():
    import bpreflight

    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert bpreflight.__version__


def test_subcommand_required():
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args([])
    assert excinfo.value.code == 2


def test_unknown_format_is_rejected_by_parser(tmp_path):
    spec = tmp_path / "s.json"
    spec.write_text('{"schema": "bpreflight/spec/1"}', encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(
            ["report", "--input", str(spec), "--format", "html"]
        )
    assert excinfo.value.code == 2


def test_missing_input_file_returns_usage_error(tmp_path, capsys):
    missing = tmp_path / "nope.json"
    code = main(["check", "--input", str(missing)])
    assert code == 3
    err = capsys.readouterr().err
    assert "no fallback" in err


def test_non_json_extension_is_rejected_without_sniffing(tmp_path, capsys):
    path = tmp_path / "spec.toml"
    path.write_text('symbol = "ean13"', encoding="utf-8")
    code = main(["check", "--input", str(path)])
    assert code == 3
    assert "no content sniffing" in capsys.readouterr().err


def test_bad_json_returns_usage_error(tmp_path, capsys):
    path = tmp_path / "spec.json"
    path.write_text("{not json", encoding="utf-8")
    code = main(["check", "--input", str(path)])
    assert code == 3
    assert "not valid JSON" in capsys.readouterr().err


def test_unknown_schema_is_rejected(tmp_path, capsys):
    path = tmp_path / "spec.json"
    path.write_text('{"schema": "other/1"}', encoding="utf-8")
    code = main(["check", "--input", str(path)])
    assert code == 3
    assert "unsupported schema" in capsys.readouterr().err


def test_unsupported_symbol_is_rejected(tmp_path, capsys):
    """首期范围外的符号显式拒绝（§8.9 G4），不猜。"""
    path = tmp_path / "spec.json"
    path.write_text(
        '{"schema": "bpreflight/spec/1", "symbol": "aztec"}', encoding="utf-8"
    )
    code = main(["check", "--input", str(path)])
    assert code == 3
    assert "unsupported symbol" in capsys.readouterr().err


def test_json_switch_requires_out_dir_to_exist(tmp_path, capsys, monkeypatch):
    """落点是固定路径 `out/`；目录不存在即 exit 3，且零副作用（不静默建目录）。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "spec.json"
    spec.write_text('{"schema": "bpreflight/spec/1"}', encoding="utf-8")
    code = main(["check", "--input", str(spec), "--json"])
    assert code == 3
    assert "does not exist" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_json_and_md_switches_write_fixed_paths(tmp_path, monkeypatch):
    """开关只决定"写不写"，不决定"写到哪"（决策 D20）。"""
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "spec.json"
    spec.write_text(
        '{"schema": "bpreflight/spec/1", "symbol": "ean13"}', encoding="utf-8"
    )
    (tmp_path / "out").mkdir()
    code = main(["check", "--input", str(spec), "--json", "--md"])
    assert code == 0
    assert (tmp_path / "out" / "report.json").read_text(encoding="utf-8").startswith("{")
    assert (tmp_path / "out" / "report.md").read_text(encoding="utf-8").startswith(
        "VERDICT: "
    )


def test_report_paths_are_not_configurable(tmp_path, capsys):
    """路径参数已退役：给 `--json` 传值必须是 argparse 的用法错误。

    这条判据同时钉住"落点不来自 argv"这条结构性约定——有人把 `--json` 改回
    `metavar=PATH` 的取值式，这条立刻红（决策 D20）。
    """
    spec = tmp_path / "spec.json"
    spec.write_text('{"schema": "bpreflight/spec/1"}', encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        main(["check", "--input", str(spec), "--json", "out/report.json"])
    assert excinfo.value.code == 2


def test_oracle_artifacts_are_fixed_paths(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "spec.json"
    spec.write_text('{"schema": "bpreflight/spec/1"}', encoding="utf-8")
    (tmp_path / "out").mkdir()
    code = main(["oracle", "--input", str(spec)])
    assert code == 0
    text = (tmp_path / "out" / "oracle-report.md").read_text(encoding="utf-8")
    assert "oracle_absent" in text


def test_oracle_requires_out_dir(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "spec.json"
    spec.write_text('{"schema": "bpreflight/spec/1"}', encoding="utf-8")
    code = main(["oracle", "--input", str(spec)])
    assert code == 3
    assert "does not exist" in capsys.readouterr().err


def test_check_prints_markdown_by_default(tmp_path, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text(
        '{"schema": "bpreflight/spec/1", "symbol": "ean13"}', encoding="utf-8"
    )
    code = main(["check", "--input", str(spec)])
    out = capsys.readouterr().out
    assert out.startswith("VERDICT: ")
    # 骨架期必然 fail（决策 D16）：没有判定层时不允许冒充 pass。
    assert "VERDICT: fail" in out
    assert code == 0  # 默认 --fail-on=none 只报告不拦


def test_report_format_json_goes_to_stdout(tmp_path, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text('{"schema": "bpreflight/spec/1"}', encoding="utf-8")
    main(["report", "--input", str(spec), "--format", "json"])
    out = capsys.readouterr().out
    assert out.lstrip().startswith("{")


def _readme_commands():
    """抽 README 代码块里的 `bpreflight ...` 命令行（不含注释与续行）。"""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    commands = []
    for block in re.findall(r"```(?:bash|sh|console)?\n(.*?)```", readme, re.S):
        for line in block.splitlines():
            line = line.strip()
            if not line.startswith("bpreflight "):
                continue
            if "<" in line or ">" in line:  # 占位符行不参与反射
                continue
            commands.append(line)
    return commands


def test_readme_commands_parse_with_real_parser(tmp_path):
    """README 的每条 `bpreflight` 命令都必须能被真实 parser 解析（成本极低，能抓住参数面不一致）。"""
    commands = _readme_commands()
    assert commands, "README 里找不到任何 bpreflight 命令（反射对账扫了 0 条 = 空跑）"
    parser = build_parser()
    for command in commands:
        argv = command.split()[1:]
        # 把路径占位替换成真实存在的临时文件，避免"解析成功但文件不存在"掩盖参数面问题。
        real = []
        for token in argv:
            if token.endswith(".json"):
                path = tmp_path / "spec.json"
                path.write_text('{"schema": "bpreflight/spec/1"}', encoding="utf-8")
                real.append(str(path))
            else:
                real.append(token)
        try:
            parser.parse_args(real)
        except SystemExit as exc:  # argparse 用 SystemExit 报错
            raise AssertionError(
                "README command does not parse: {!r} (exit {})".format(command, exc.code)
            )
