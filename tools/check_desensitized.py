#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""脱敏门：入库文本不得含本机盘符 / MSYS 用户路径 / 本机用户名 / 回环代理。

为什么是常驻门而不是发布前 grep 一次：这些位置在每次续接对话里都会被追加
（环境坑章节天然要写"本机是 3.8"这类事实），所以必须每次可跑红。

四条规则（`references/methodology-binding.md` ③b）：

  1. `drive-absolute`  盘符绝对路径（`C:\\...` / `D:/...`）
  2. `msys-user-path`  `/c/Users/...` 形式
  3. `local-username`  本机用户名出现在路径里
  4. `loopback-proxy`  回环地址带端口（`127.0.0.1:7897` 这类）

四条口径：
  · **占位符必须放行**：`C:\\Users\\<user>\\…`、`<repo>` 是脱敏后的正确写法；
  · 公开镜像（`pypi.tuna…` / `goproxy.cn`）不在判据内，只认回环/私网；
  · **门要豁免自己**，并把豁免份数打进结论行；
  · 扫描面 = 入库文本（跳过 `.git/`、venv、构建产物），不是"本地环境"。
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 门自身与同族的变异脚本必须写出被判据禁止的字面量 —— **逐条列全**
#: （面是"文件集合"，不是单个文件名；`references/methodology-binding.md` ③b.3）。
SELF_EXEMPT = {
    "tools/check_desensitized.py",
    "tools/verify_gates.py",
}

#: 扫描面：入库文本。新增本地产物目录时必须同步收编到这里（否则下次还会红）。
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "build",
    "dist",
    ".tox",
    ".nox",
    "out",
    "reports",
    "runs",
    "release",
    ".tmp",
    ".mimosa",
    ".claude",
    ".zcode",
}

#: 名字随包名变的产物用后缀匹配（逐个写死会漏）。
SKIP_SUFFIXES = (".egg-info", ".dist-info", ".pyc", ".pyo")

#: 只扫文本类文件。
TEXT_SUFFIXES = (
    ".md",
    ".py",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".in",
    ".cfg",
    ".ini",
    ".mjs",
    ".js",
    ".sh",
    ".ps1",
    ".gitignore",
    "",
)

RULES = [
    (
        "drive-absolute",
        # 盘符绝对路径；`<` 开头的是占位符（脱敏后的正确写法），负向前瞻放行。
        re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?!<)(?:[^\s`'\"()\[\]<>]*)"),
    ),
    (
        "msys-user-path",
        re.compile(r"/[a-z]/Users/(?!<)[^\s`'\"()\[\]<>]*"),
    ),
    (
        "local-username",
        re.compile(r"Users[\\/](?!<)(?!(?:Public|Default|All Users)\b)[A-Za-z0-9_.-]{2,}"),
    ),
    (
        "loopback-proxy",
        re.compile(r"\b(?:127\.0\.0\.1|localhost|0\.0\.0\.0):\d{2,5}\b"),
    ),
]

#: 允许的公开镜像（不是私有代理）。
ALLOWED = (
    "pypi.tuna.tsinghua.edu.cn",
    "goproxy.cn",
    "registry.npmjs.org",
)


def iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIRS and not d.endswith(SKIP_SUFFIXES)
        )
        for name in sorted(filenames):
            if any(name.endswith(suffix) for suffix in SKIP_SUFFIXES):
                continue
            suffix = os.path.splitext(name)[1]
            if suffix and suffix not in TEXT_SUFFIXES and name != ".gitignore":
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/")
            yield rel


def _token_around(line, match):
    """取命中所在的空白分隔 token（含 `\\` 与 `/` 分隔的整段），用于判断占位符。"""
    start = match.start()
    end = match.end()
    while start > 0 and not line[start - 1].isspace():
        start -= 1
    while end < len(line) and not line[end].isspace():
        end += 1
    return line[start:end]


def scan():
    hits = []
    scanned = 0
    exempted = 0
    for rel in iter_files():
        if rel in SELF_EXEMPT:
            exempted += 1
            continue
        path = os.path.join(ROOT, rel)
        try:
            with io.open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        scanned += 1
        if any(allowed in text for allowed in ALLOWED):
            # 只把"允许镜像"那一段剥掉后再扫，避免整文件放行。
            for allowed in ALLOWED:
                text = text.replace(allowed, "<allowed-mirror>")
        for number, line in enumerate(text.splitlines(), start=1):
            for rule_name, pattern in RULES:
                match = pattern.search(line)
                if not match:
                    continue
                # 占位符必须放行：`C:\\Users\\<user>\\…` 是脱敏后的正确写法。
                # 判据看**整个 token**，不能只看匹配片段——正则会在 `<` 处截断。
                if "<" in _token_around(line, match):
                    continue
                hits.append((rel, number, rule_name, match.group(0)))
                break
    return hits, scanned, exempted


def main():
    hits, scanned, exempted = scan()
    out = io.StringIO()
    out.write("脱敏门 · 扫描面 = 入库文本\n")
    out.write("=" * 60 + "\n")
    if hits:
        for rel, number, rule_name, snippet in hits:
            out.write("FAIL  {}:{}: [{}] {}\n".format(rel, number, rule_name, snippet))
        out.write("=" * 60 + "\n")
        out.write(
            "扫描 {} 份文件，豁免 {} 份（门自身）。命中 {} 处。\n".format(
                scanned, exempted, len(hits)
            )
        )
        out.write("结论: FAIL\n")
        sys.stdout.write(out.getvalue())
        return 1
    out.write(
        "PASS  扫描 {} 份文件，豁免 {} 份（门自身），0 处命中（规则 4 条）\n".format(
            scanned, exempted
        )
    )
    out.write("=" * 60 + "\n")
    out.write("结论: 全绿\n")
    sys.stdout.write(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
